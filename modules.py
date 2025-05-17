# import custom_module as util
import sys

from custom_module import find_index, test

courses = ['Histroy', 'Math', 'Physics', 'Compsci']

math_course_index = find_index(courses, 'Math')

print('Math course is at index = {0}'.format(math_course_index))
print(test)
print(sys.path)