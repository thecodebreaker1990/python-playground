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
    
    def __iter__(self):
        for i in range(self.size):
            yield i, self.array[i]
    
class DynamicArray:
    def __init__(self):
        self.array = []
        self.len = 0 # length user thinks array is
        self.capacity = 0 # actual size of underlying array
        self._initialize_array(4)

    def __len__(self):
        return self.len

    def __repr__(self):
        items = [self.array.get(i) for i in range(self.len)]
        return f"DynamicArray({items})"

    def _initialize_array(self, capacity):
        if capacity < 0:
            raise Exception("Capacity must be non-negative")
        self.array = StaticArray(capacity)
        self.capacity = capacity

    def _resize(self):
        new_capacity = max(1, 2 * self.capacity)
        new_array = StaticArray(new_capacity)
        for i in range(self.len):
            new_array.set(i, self.array.get(i))
        self.array = new_array
        self.capacity = new_capacity

    def append(self, value):
        if self.len >= self.capacity:
            self._resize()
        self.array.set(self.len, value)
        self.len += 1

    def get(self, index):
        if index < 0 or index >= self.len:
            raise IndexError("Index out of bounds")
        return self.array.get(index)

    def set(self, index, value):
        if index < 0 or index >= self.len:
            raise IndexError("Index out of bounds")
        self.array.set(index, value)


    def clear(self):
        for i in range(self.capacity):
            self.array.set(i, None)
        self.len = 0

    def remove_at_index(self, index):
        if index < 0 or index >= self.len:
            raise IndexError("Index out of bounds")

        data = self.array.get(index)

        # shift left
        for i in range(index, self.len - 1):
            self.array.set(i, self.array.get(i + 1))

        # clear last slot
        self.array.set(self.len - 1, None)
        self.len -= 1

        # optional shrink
        if self.len > 0 and self.len <= self.capacity // 4:
            self._resize_to(max(4, self.capacity // 2))

        return data

    
    def remove(self, value):
        for i in range(self.len):
            if self.array.get(i) == value:
                self.remove_at_index(i)
                return True
        return False
    
    def index_of(self, value):
        for i in range(self.len):
            if self.array.get(i) == value:
                return i
        return -1
    
    def contains(self, value):
        return self.index_of(value) != -1
    
    def isEmpty(self):
        return self.len == 0

# Example usage:
if __name__ == "__main__":
    arr = StaticArray(5)
    arr.set(0, 'a')
    arr.set(1, 'b')
    arr.set(2, 'c')
    print(arr)  # Output: StaticArray(['a', 'b', 'c', None, None])
    print(arr.get(1))  # Output: b
    print(len(arr))  # Output: 5

    dyn_arr = DynamicArray()
    dyn_arr.append(1)
    dyn_arr.append(2)
    dyn_arr.append(3)
    dyn_arr.append(4)
    dyn_arr.append(5)  # This will trigger a resize
    print(dyn_arr)  
    dyn_arr.remove_at_index(2)
    print(dyn_arr)
    print(dyn_arr.contains(2))
    print(dyn_arr.index_of(3))