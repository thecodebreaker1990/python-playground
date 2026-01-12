class StaticArray:
    def __init__(self, size):
        self.size = size
        self.array = [None] * size

    def get(self, index):
        if 0 <= index < self.size:
            return self.array[index]
        else:
            raise IndexError("Index out of bounds")

    def set(self, index, value):
        if 0 <= index < self.size:
            self.array[index] = value
        else:
            raise IndexError("Index out of bounds")

    def __len__(self):
        return self.size

    def __repr__(self):
        return f"StaticArray({self.array})"
    
# Example usage:
if __name__ == "__main__":
    arr = StaticArray(5)
    arr.set(0, 'a')
    arr.set(1, 'b')
    arr.set(2, 'c')
    print(arr)  # Output: StaticArray(['a', 'b', 'c', None, None])
    print(arr.get(1))  # Output: b
    print(len(arr))  # Output: 5