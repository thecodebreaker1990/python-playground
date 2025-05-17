multi_line_message = """Bobby's World was a good
cartoon in the 1990s"""

message = 'Hello World'

print(len(message))
print(message[6:])
print(message.lower())
print(message.upper())
print(message.count('l'))
print(message.find('Hello'))

updated_message = message.replace('World', 'Universe')
print(updated_message)
print(updated_message.find('Universe'))

greeting = 'Hello'
name = 'Alapan'
greeting_message = f'{greeting}, {name.upper()}. Welcome!'
print(dir(name))
print(help(str.lower))
print(greeting_message)