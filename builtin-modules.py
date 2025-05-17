import random
import math
import datetime
import calendar
import os

courses = ['Histroy', 'Math', 'Physics', 'Compsci']
random_course = random.choice(courses)

print(random_course)

rads = math.radians(90)
sin_rads = math.sin(rads)

print(rads)
print(sin_rads)

today = datetime.date.today()
current_year = today.year
is_current_year_leap = calendar.isleap(current_year)

print(today)
print(is_current_year_leap)

print('Current directory = {0}'.format(os.getcwd()))
print('OS Module file location = {0}'.format(os.__file__))
