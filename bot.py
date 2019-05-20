import argparse
import json
import os
from multiprocessing.pool import ThreadPool
from shutil import move

from src.costants import SCREENSHOT, INPUT_SENTENCE
from src.image_to_text import img_to_text
from src.switch import Switch
from src.utlity import files, timeit


def do_screenshot():
    return os.system("adb exec-out screencap -p > " + SCREENSHOT)


@timeit
def do_question(pool: ThreadPool, file: str = SCREENSHOT, debug: bool = False):
    instance = img_to_text(file, pool, debug)
    print(instance.question)
    switch = Switch(pool)
    switch.run(instance)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run a bootstrap node')
    sp = parser.add_mutually_exclusive_group()
    sp.add_argument('--live', help='Live game', action='store_true')
    sp.add_argument('--test', help='Test screens', action='store_true')
    sp.add_argument('--dump', help='Dump questions', action='store_true')
    args = parser.parse_args()

    pool = ThreadPool(3)

    try:
        if args.live:
            while True:
                key = input(INPUT_SENTENCE)
                if not key:
                    screen = do_screenshot()
                    if screen == 0:
                        do_question(pool)
                if key == 'q':
                    pool.close()
                    pool.join()
        elif args.test:
            for index, file in enumerate(files('test')):
                if file.split('.')[1] == 'jpg' or file.split('.')[1] == 'png':
                    do_question(pool, file, debug=False)
                    key = input()
                    if key == 'y':
                        move(file, 'screenshot/' + file.split('/')[1])
        elif args.dump:
            exists = os.path.isfile('dump.txt')
            questions = []
            if exists:
                with open('dump.txt') as json_file:
                    data = json.load(json_file, strict=False)
                    for index, file in enumerate(files('stage')):
                        if file.split('.')[1] == 'jpg' or file.split('.')[1] == 'png':
                            instance = img_to_text(file, pool, debug=False)
                            questions.append({
                                'index': index,
                                'question': instance.question,
                                'answers': [
                                    {
                                        'first_answer': instance.first_answer,
                                        'correct': False
                                    },
                                    {
                                        'second_answer': instance.second_answer,
                                        'correct': False
                                    },
                                    {
                                        'third_answer': instance.third_answer,
                                        'correct': False
                                    }
                                ]
                            })
                d = json.dumps(questions)
                with open('dump.txt', 'w') as the_file:
                    the_file.write(d)
    except KeyboardInterrupt as _:
        pool.close()
        pool.join()
        exit(0)
