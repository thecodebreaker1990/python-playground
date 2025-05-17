person = { 'name': 'Alapan', 'age': 33 }
sentence = 'My name is {0} and I am {1} years old'.format(person['name'], person['age'])

print(sentence)

tag = 'h1'
text = 'This is a headline'
formatted_tag = '<{0}>{1}</{0}>'.format(tag, text)

print(formatted_tag)

address_components = ['DLF Westend Heights Apartment', 'Bengaluru', 'Karnataka', 560068]
my_address = """My current Address is:
Building: {0[0]},
City: {0[1]},
State: {0[2]},
Pincode: {0[3]}
""".format(address_components)

print(my_address)

class Person():

    def __init__(self, name, age):
        self.name = name
        self.age = age

p1 = Person('Jack', 33)
person_details = 'My name is {0.name} and I am {0.age} years old'.format(p1)

print(person_details)

storage = {'type': 'local', 'limit': '10MB'}
storage_details = 'Browser supports {type} storage, with a limit up to {limit}'.format(**storage)

print(storage_details)

for i in range(1, 11):
    value_details = 'The value is {:02}'.format(i)
    print(value_details)

pi = 3.14159265
formatted_pi_value = 'Pi is equal to {:.3f}'.format(pi)

print(formatted_pi_value)

file_size_description = '1 MB is equal to {:,.2f} bytes'.format(1000 ** 2)
print(file_size_description)

import datetime
my_date = datetime.datetime(2016, 9, 24, 12, 30, 45)
formatted_date = '{:%B %d, %Y}'.format(my_date)

print(formatted_date)