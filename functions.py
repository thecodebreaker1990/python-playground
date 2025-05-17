def log_message(message):
    print(message)

def hello_func(greeting, name = 'You'):
    return '{0}, {1}.'.format(greeting, name)

def student_info(*args, **kwargs):
    print(args)
    print(kwargs)

log_message('Hello World!')
log_message('Hello Function!')

message = hello_func('Hello').upper()
message_length = len(message)
print('Message = {0}, Message length = {1}'.format(message, message_length))

courses = ['Math', 'Art']
info = {'name': 'Alapan', 'age': 33}

student_info(*courses, **info)