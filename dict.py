student = {'name': 'Alapan', 'age': 33, 'courses': ['Math', 'CompSci'], 1: 'Weird!'}

student['phone'] = '+91-9804190912'

# Update the student details
student.update({'name': 'Jane', 'age': 26})

# delete a specific key from the dict
del student['phone']

# pop a specific value from the student object 
age = student.pop('age')

for key, value in student.items():
    print(key, value)

print(student.get('phone', 'Not Found'))
print(age)
print(student)