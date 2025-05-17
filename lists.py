courses = ['History', 'Math', 'Physics', 'CompSci']
courses_2 = ['Art', 'Education']

print(courses[-1])
print(len(courses))
print(courses[0:2])
print(courses[2:])

courses.append('English')
print(courses)

courses.extend(courses_2)
print(courses)

#remove item from list
courses.remove('Math')
print(courses)

#get last item from list and modify original list
last_course = courses.pop()
print(last_course)

#reverse list
courses.reverse()
print(courses)

#sort list (in-place)
nums = [1, 5, 2, 4, 3]
nums.sort(reverse=True)
print(nums)

#sort list(return new list)
sorted_courses = sorted(courses)
print(sorted_courses)

#find index of a specific item
course_art_idx = courses.index('Art')
print(course_art_idx)

#check if item exists in list
print('Math' in courses)

#loop through all items
for index, course in enumerate(courses):
    print(f'Course index = {index}, Course name = {course.upper()}')

#list to string
course_str = ', '.join(courses)
print(course_str)

#string to list
new_list = course_str.split(', ')
print(new_list)