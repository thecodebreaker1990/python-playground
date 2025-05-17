language = 'Java'

if language == 'Python':
    print('First Langauge is Python')
elif language == 'Java':
    print('Second Langauge is Java')
else:
    print('No Match')

user = 'admin'
logged_in = False

if not logged_in:
    print('Please Log In')
else:
    print('Welcome')

if user == 'admin' and logged_in:
    print('Admin Page')
else:
    print('Bad Creds')

a = [1, 2, 3]
b = [1, 2, 3]
c = a

#  id function returns the memory location of a variable 
print(id(a))
print(id(b))
print(a is b)
print(a is c)