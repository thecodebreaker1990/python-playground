# Sets
cs_courses = {'Python', 'Time Complexity', 'DSA', 'Math'}
# Art Courses
art_courses = {'History', 'Math', 'Art', 'Design'}

common_courses = cs_courses.intersection(art_courses)
unique_cs_courses = cs_courses.difference(art_courses)
combined_courses = cs_courses.union(art_courses)

print('Common Courses = {0}'.format(common_courses))
print('Special Subject in CS Courses = {0}'.format(unique_cs_courses))
print('Combined Courses = {0}'.format(combined_courses))

