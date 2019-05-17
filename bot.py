import argparse
import json
import operator
import os
import random
import re
import string
import time
from multiprocessing.pool import ThreadPool
from shutil import copyfile

import PIL
import nltk
import requests
import unidecode
from PIL import Image
from bs4 import BeautifulSoup
from pytesseract import pytesseract
from num2words import num2words

SCREENSHOT = 'screenshot.png'
QUESTION_BOUNDARIES = lambda w, h: (35, 450, w - 35, h - 1170)
FIRST_ANSWER_BOUNDARIES = lambda w, h, space: (35, 690 + space, w - 120, h - 1050 + space)
SECOND_ANSWER_BOUNDARIES = lambda w, h, space: (35, 910 + space, w - 120, h - 830 + space)
THIRD_ANSWER_BOUNDARIES = lambda w, h, space: (35, 1130 + space, w - 120, h - 610 + space)
BETWEEN_MODE_TERMS = ['tra quest', 'quale di quest', 'fra questi', 'tra loro', 'seleziona', 'tra i seguenti',
                      'in quale', 'chi tra']
COORD_MODE_TERMS = ['nord', 'sud', 'ovest', 'est']

DOMAIN = "https://www.google.it/search?q="

COMMA_REMOVE = ['come', 'perche', 'quando', 'chi', 'cosa', 'quale', 'qual']

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,it;q=0.8,la;q=0.7',
    'Accept-Encoding': 'gzip, deflate',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

it_stop_words = nltk.corpus.stopwords.words('italian') + ['dell', 'indica', 'vera', 'l\'affermazione', 'i', 'la',
                                                          'queste', 'questo', 'questi', 'in', 'quale', 'quali', 'l',
                                                          '\'', '\"', '``', '\'', '`', 'fra', 'l\'']


def timeit(method):
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        if 'log_time' in kw:
            name = kw.get('log_name', method.__name__.upper())
            kw['log_time'][name] = int((te - ts) * 1000)
        else:
            print('%r  %2.2f ms' %
                  (method.__name__, (te - ts) * 1000))
        return result

    return timed


def clean(text):
    word_tokenized_list = nltk.tokenize.word_tokenize(text)

    word_tokenized_no_punct = [x.lower() for x in word_tokenized_list if x not in string.punctuation]

    word_tokenized_no_punct_no_sw = [x for x in word_tokenized_no_punct if x not in set(it_stop_words + it_stop_words)]

    word_tokenized_no_punct_no_sw_no_apostrophe = [x.split("'") for x in word_tokenized_no_punct_no_sw]
    word_tokenized_no_punct_no_sw_no_apostrophe = [y for x in word_tokenized_no_punct_no_sw_no_apostrophe for y in x]

    return ' '.join(unidecode.unidecode(' '.join(word_tokenized_no_punct_no_sw_no_apostrophe)).split())


class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


def files(path):
    files = []
    for r, d, f in os.walk(path):
        for file in f:
            files.append(os.path.join(r, file))
    return files


def do_screenshot():
    return os.system("adb exec-out screencap -p > " + SCREENSHOT)


def crop_image(img, area):
    return img.crop(area)


def question_image_to_text(img, area):
    question_image = crop_image(img, area)
    # question_image.show()
    question_text = pytesseract.image_to_string(question_image, lang='ita')
    n_of_lines = question_text.count('\n') + 1
    question_text = question_text.replace('\n', ' ')
    n_of_lines_space = (n_of_lines - 1) * 40 + (25 if n_of_lines == 3 else 0)
    return question_text, n_of_lines_space


def answer_image_to_text(data):
    answer_image = crop_image(data[0], data[1])
    answer_text = pytesseract.image_to_string(answer_image, lang='ita').replace('\n', ' ')
    if answer_text == "":
        w, h = answer_image.size
        answer_image = crop_image(answer_image, (60, 20, 0.2 * w, h - 30)) # (35, 450, w - 35, h - 1170)
        # answer_image.show()
        answer_text = pytesseract.image_to_string(answer_image, lang='ita', config='--psm 6').replace('\n', ' ')
    return answer_text


def unpack_texts(texts):
    return texts[0], texts[1], texts[2], texts[3]


def select_modes(question):
    question_lower = question.lower()
    NEGATIVE_MODE = 'NON' in question
    QUERY_MODE = 'BETWEEN' if any(term in question_lower for term in BETWEEN_MODE_TERMS) else 'DEFAULT'
    QUERY_MODE = 'TERZETTO' if 'terzetto' in question and question.count("\"") == 4 else QUERY_MODE
    QUERY_MODE = 'COORD' if any(term in question_lower for term in COORD_MODE_TERMS) else QUERY_MODE
    return NEGATIVE_MODE, QUERY_MODE


def craft_query_google(mode, question, answers):
    if mode == 'BETWEEN':
        return [DOMAIN + question, DOMAIN + question + ' AND (' + (answers[0] + ' OR ' if answers[0] != '' else '') + (
            answers[1] + ' OR ' if answers[1] != '' else '') + (
                   answers[2] if answers[2] != '' else '') + ')']
    if mode == 'TERZETTO':
        return [
            DOMAIN + question.replace('completa terzetto ', '') + ' AND ' + answers[0],
            DOMAIN + question + ' AND ' + answers[1],
            DOMAIN + question + ' AND ' + answers[2],
        ]
    if mode == 'COORD':
        return [DOMAIN + answers[0] + ' coordinates',
                DOMAIN + answers[1] + ' coordinates',
                DOMAIN + answers[2] + ' coordinates'
        ]
    else:
        return [DOMAIN + question]


def get_answer_google(data):
    query = data[0].replace(' ', '+')

    r = requests.get(query, headers=headers)
    soup = BeautifulSoup(r.text, features="html.parser")
    all_links = soup.find_all('div', {'class': 'g'})
    if data[4] == 'COORD':
        return soup.find('div', {'class', 'Z0LcW'}).text.strip()
    points = {
        data[1]: 0,
        data[2]: 0,
        data[3]: 0
    }

    for link in all_links:
        try:
            title = link.find('div', {'class': 'r'}).find('h3').text.lower()
            description = link.find('div', {'class': 's'}).find('span', {'class': 'st'}).text.lower()
        except Exception as e:
            continue



        for answer in points.keys():
            if answer == ''.strip(): continue
            count_title = 0
            count_description = 0
            c_title = clean(title)
            c_description = clean(description)
            if data[4] == 'DEFAULT' or data[4] == 'BETWEEN':
                for a in answer.lower().split(' '):
                    if a.strip() != '' and (len(a) > 1 or a.isdigit()):
                        count_title += sum(1 for _ in re.finditer(r'\b%s\b' % re.escape(a), c_title))
                        if a.isdigit():
                            int_to_word = num2words(int(a), lang='it')
                            count_title += sum(1 for _ in re.finditer(r'\b%s\b' % re.escape(int_to_word), c_title))
                for a in answer.lower().split(' '):
                    if a.strip() != ''  and (len(a) > 1 or a.isdigit()):
                        count_description = + sum(1 for _ in re.finditer(r'\b%s\b' % re.escape(a), c_description))
                        if a.isdigit():
                            int_to_word = num2words(int(a), lang='it')
                            count_description += sum(1 for _ in re.finditer(r'\b%s\b' % re.escape(int_to_word), c_title))

                points[answer] += count_title + count_description
            elif data[4] == 'TERZETTO':
                count_title += sum(1 for _ in re.finditer(r'\b%s\b' % re.escape(answer), c_title))
                count_description = + sum(1 for _ in re.finditer(r'\b%s\b' % re.escape(answer), c_description))
                points[answer] += count_title + count_description

    return points


def print_results(points, NEGATIVE_MODE):
    if NEGATIVE_MODE:
        res = list(sorted(points.items(), key=operator.itemgetter(1)))
    else:
        res = list(reversed(sorted(points.items(), key=operator.itemgetter(1))))

    print('{}1: {}{} - score: {}'.format(Colors.BOLD + Colors.GREEN, res[0][0].upper(), Colors.END, res[0][1]))
    print('{}2: {}{}- score: {}'.format(Colors.BOLD + Colors.RED, res[1][0].upper(), Colors.END, res[1][1]))
    print('{}3: {}{} - score: {}'.format(Colors.BOLD + Colors.RED, res[2][0].upper(), Colors.END, res[2][1]))


def random_string(N=16):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=N))


@timeit
def do_question(pool, file=SCREENSHOT, debug=False):
    if not debug: copyfile('screenshot.png', 'screenshot/' + random_string() + '.png')
    img = Image.open(file)
    img = img.convert('LA')
    img = img.resize((1280, 1920), PIL.Image.ANTIALIAS)
    img_a = img.point(lambda x: 0 if x < 140 else 255)

    w, h = img.size
    question_text, space = question_image_to_text(img, QUESTION_BOUNDARIES(w, h))

    answers_text = pool.map(answer_image_to_text, [
        [img_a, FIRST_ANSWER_BOUNDARIES(w, h, space)],
        [img_a, SECOND_ANSWER_BOUNDARIES(w, h, space)],
        [img_a, THIRD_ANSWER_BOUNDARIES(w, h, space)]
    ])
    if debug: print(*[question_text] + answers_text, sep='\n')

    NEGATIVE_MODE, QUERY = select_modes(question_text)


    if QUERY == "DEFAULT":
        question = question_text.lower().split(', ')
        for q in question:
            if any(word in q for word in COMMA_REMOVE):

                question_text = q
                break

    texts_clean = pool.map(clean, [question_text] + answers_text)
    question_text, first_answer_text, second_answer_text, third_answer_text = unpack_texts(texts_clean)

    queries = craft_query_google(QUERY, question_text, [first_answer_text, second_answer_text, third_answer_text])
    print(queries)


    total_points = {}
    if len(queries) == 2:
        points = pool.map(get_answer_google, [
            [queries[0], first_answer_text, second_answer_text, third_answer_text, 'BETWEEN'],
            [queries[1], first_answer_text, second_answer_text, third_answer_text, 'BETWEEN']
        ])
        if list(points[0].values()).count(0) == 2 and not NEGATIVE_MODE:
            total_points = points[0]
        elif list(points[1].values()).count(0) == 2 and not NEGATIVE_MODE:
            total_points = points[1]
        else:
            total_points = {k: points[0].get(k, 0) + points[1].get(k, 0) for k in set(points[0]) | set(points[1])}
    elif len(queries) == 1:
        points = pool.map(get_answer_google, [
            [queries[0], first_answer_text, second_answer_text, third_answer_text, 'DEFAULT']
        ])
        total_points = points[0]
    elif len(queries) == 3:
        if QUERY == 'COORD':
            coordinates = pool.map(get_answer_google, [
                [queries[0], first_answer_text, second_answer_text, third_answer_text, 'COORD'],
                [queries[1], first_answer_text, second_answer_text, third_answer_text, 'COORD'],
                [queries[2], first_answer_text, second_answer_text, third_answer_text, 'COORD']
            ])
            total_points = get_points_from_coords(question_text, coordinates, [first_answer_text, second_answer_text, third_answer_text])
        else:
            points = pool.map(get_answer_google, [
                [queries[0], first_answer_text , second_answer_text, third_answer_text, 'TERZETTO'],
                [queries[1], first_answer_text, second_answer_text, third_answer_text, 'TERZETTO'],
                [queries[2], first_answer_text, second_answer_text, third_answer_text, 'TERZETTO']
            ])
            total_points = {k: points[0].get(k, 0) + points[1].get(k, 0) for k in set(points[0]) | set(points[1])}
            total_points = {k: total_points.get(k, 0) + points[2].get(k, 0) for k in set(total_points) | set(points[2])}

    print_results(total_points, NEGATIVE_MODE)


def get_texts(file, pool=ThreadPool(3)):
    img = Image.open(file)
    img = img.convert('LA')
    img = img.resize((1280, 1920), PIL.Image.ANTIALIAS)
    img_a = img.point(lambda x: 0 if x < 140 else 255)

    w, h = img.size
    question_text, space = question_image_to_text(img, QUESTION_BOUNDARIES(w, h))

    answers_text = pool.map(answer_image_to_text, [
        [img_a, FIRST_ANSWER_BOUNDARIES(w, h, space)],
        [img_a, SECOND_ANSWER_BOUNDARIES(w, h, space)],
        [img_a, THIRD_ANSWER_BOUNDARIES(w, h, space)]
    ])

    return unpack_texts([question_text] + answers_text)

def get_points_from_coords(question, coordinates, answers):
    direction = list(filter(lambda x: x in COORD_MODE_TERMS, question.split(' ')))[0]
    south_bucket = []
    east_bucket = []
    north_bucket = []
    west_bucket = []
    answer_dict = {}

    for idx, coordinate in enumerate(coordinates):
        latLong = coordinate.split(', ')
        lat_orientation = latLong[0].split('° ')[1]
        lat_value = float(latLong[0].split('° ')[0])
        lon_orientation = latLong[1].split('° ')[1]
        lon_value = float(latLong[1].split('° ')[0])
        answer_dict[lat_value] = idx
        answer_dict[lon_value] = idx
        if lat_orientation == 'S':
            south_bucket.append(lat_value)
        elif lat_orientation == 'N':
            north_bucket.append(lat_value)
        if lon_orientation == 'W':
            west_bucket.append(lon_value)
        elif lon_orientation == 'E':
            east_bucket.append(lon_value)

    lowest_value = 0
    if direction == 'sud':
        if len(south_bucket) > 0:
            south_bucket.sort(reverse=True)
            lowest_value = south_bucket[0]
        else:
            north_bucket.sort()
            lowest_value = north_bucket[0]
    elif(direction == 'nord'):
        if len(north_bucket) > 0:
            north_bucket.sort(reverse=True)
            lowest_value = north_bucket[0]
        else:
            south_bucket.sort()
            lowest_value = south_bucket[0]
    elif (direction == 'est'):
        if len(east_bucket) > 0:
            east_bucket.sort(reverse=True)
            lowest_value = east_bucket[0]
        else:
            west_bucket.sort()
            lowest_value = west_bucket[0]
    elif (direction == 'ovest'):
        if len(west_bucket) > 0:
            west_bucket.sort(reverse=True)
            lowest_value = west_bucket[0]
        else:
            east_bucket.sort()
            lowest_value = east_bucket[0]

    lowest_answer = answer_dict[lowest_value]

    return {
        answers[0]: 1 if lowest_answer == 0 else 0,
        answers[1]: 1 if lowest_answer == 1 else 0,
        answers[2]: 1 if lowest_answer == 2 else 0,
    }


def do_answer(question_text, answers_text, right_answer):
    NEGATIVE_MODE, QUERY = select_modes(question_text)

    if QUERY == "DEFAULT":
        question = question_text.lower().split(', ')
        for q in question:
            if any(word in q for word in COMMA_REMOVE):
                question_text = q
                break

    texts_clean = pool.map(clean, [question_text] + answers_text)
    question_text, first_answer_text, second_answer_text, third_answer_text = unpack_texts(texts_clean)

    queries = craft_query_google(QUERY, question_text, [first_answer_text, second_answer_text, third_answer_text])
    print(queries)

    total_points = {}
    if len(queries) == 2:
        points = pool.map(get_answer_google, [
            [queries[0], first_answer_text, second_answer_text, third_answer_text, 'BETWEEN'],
            [queries[1], first_answer_text, second_answer_text, third_answer_text, 'BETWEEN']
        ])
        if list(points[0].values()).count(0) == 2 and not NEGATIVE_MODE:
            total_points = points[0]
        elif list(points[1].values()).count(0) == 2 and not NEGATIVE_MODE:
            total_points = points[1]
        else:
            total_points = {k: points[0].get(k, 0) + points[1].get(k, 0) for k in set(points[0]) | set(points[1])}
    elif len(queries) == 1:
        points = pool.map(get_answer_google, [
            [queries[0], first_answer_text, second_answer_text, third_answer_text, 'DEFAULT']
        ])
        total_points = points[0]
    elif len(queries) == 3:
        if QUERY == 'COORD':
            coordinates = pool.map(get_answer_google, [
                [queries[0], first_answer_text, second_answer_text, third_answer_text, 'COORD'],
                [queries[1], first_answer_text, second_answer_text, third_answer_text, 'COORD'],
                [queries[2], first_answer_text, second_answer_text, third_answer_text, 'COORD']
            ])
            total_points = get_points_from_coords(question_text, coordinates, [first_answer_text, second_answer_text, third_answer_text])
        else:
            points = pool.map(get_answer_google, [
                [queries[0], first_answer_text, second_answer_text, third_answer_text, 'TERZETTO'],
                [queries[1], first_answer_text, second_answer_text, third_answer_text, 'TERZETTO'],
                [queries[2], first_answer_text, second_answer_text, third_answer_text, 'TERZETTO']
            ])
            total_points = {k: points[0].get(k, 0) + points[1].get(k, 0) for k in set(points[0]) | set(points[1])}
            total_points = {k: total_points.get(k, 0) + points[2].get(k, 0) for k in set(total_points) | set(points[2])}

    print_results(total_points, NEGATIVE_MODE)

    print(total_points)

    if NEGATIVE_MODE:
        res = list(sorted(total_points.items(), key=operator.itemgetter(1)))
    else:
        res = list(reversed(sorted(total_points.items(), key=operator.itemgetter(1))))
    return res[0][0].lower() == clean(right_answer['text'].lower())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run a bootstrap node')
    sp = parser.add_mutually_exclusive_group()
    sp.add_argument('--live', help='Live game', action='store_true')
    sp.add_argument('--test', help='Test screens', action='store_true')
    sp.add_argument('--dump', help='Dump screens', action='store_true')
    sp.add_argument('--feature', help='Dump screens', action='store_true')
    sp.add_argument('--test-id', help='Dump screens', type=int)
    args = parser.parse_args()

    pool = ThreadPool(3)
    try:
        if args.live:
            while True:
                key = input("Press " + Colors.BOLD + Colors.GREEN + "ENTER" + Colors.END + " to take a screenshot" +
                            " of the question or press " + Colors.BOLD + Colors.RED + "q" + Colors.END + " to quit: ")
                if not key:
                    screen = do_screenshot()
                    if screen == 0:
                        do_question(pool, debug=False)
                if key == 'q':
                    pool.close()
                    pool.join()
        elif args.test:
            with open('dump.txt') as json_file:
                data = json.load(json_file, strict=False)
                total = len(data)
                right = 0
                not_right = []
                for question in data:
                    right_answer = list(filter(lambda x: x['correct'] == True, question['answers'].values()))
                    if len(right_answer) == 0: continue
                    else: right_answer = right_answer[0]
                    res = do_answer(question['question'],
                              [question['answers']['A']['text'], question['answers']['B']['text'], question['answers']['C']['text']],
                              right_answer)
                    if res:
                        right += 1
                        print('ok')
                    else:
                        print(question)
                        not_right.append(question)
                print('{} out of {} have been answered correctly ({})'.format(right, total, right/total))
                print(*not_right, sep='\n')
            pool.close()
            pool.join()
        elif args.dump:
            data = []
            for index, file in enumerate(files('screenshot')):
                print(file)
                texts = get_texts(file)
                q = {
                    'index': index,
                    'question': texts[0],
                    'answers': {
                        'A': {
                            'text': texts[1],
                            'correct': False
                        },
                        'B': {
                            'text': texts[2],
                            'correct': False
                        },
                        'C': {
                            'text': texts[3],
                            'correct': False
                        }
                    }
                }
                data.append(q)
            with open("dump.txt", 'w+') as f:
                f.write(json.dumps(data))
            pool.close()
            pool.join()
        elif args.test_id:
            with open('dump.txt') as json_file:
                data = json.load(json_file, strict=False)
                print(data)
                for question in data:
                    if str(question['index']) != str(args.test_id): continue
                    right_answer = list(filter(lambda x: x['correct'] == True, question['answers'].values()))
                    if len(right_answer) == 0: continue
                    else: right_answer = right_answer[0]
                    res = do_answer(question['question'],
                              [question['answers']['A']['text'], question['answers']['B']['text'], question['answers']['C']['text']],
                              right_answer)
                    if res == False:
                        print(question)
                    else:
                        print('ok')
                    break
            pool.close()
            pool.join()
        elif args.feature:
            for index, file in enumerate(files('feature')):
                if file.split('.')[1] == 'jpg' or file.split('.')[1] == 'png':
                    do_question(pool, file, debug=True)
    except KeyboardInterrupt as _:
        pool.close()
        pool.join()
        exit(0)
