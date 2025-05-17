print('Imported my module...')

test = 'Test String'

def find_index(haystack, needle):
    """Find the index of a value in a sequence"""
    for i, value in enumerate(haystack):
        if value == needle:
            return i
        
    return -1