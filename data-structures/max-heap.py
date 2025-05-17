import random
class BinaryHeap:
    def __init__(self):
        self.values = []
        self.heap_length = 0

    def __str__(self):
        return ", ".join(map(str, self.values[0:self.heap_length]))

    def insert(self, value):
        self.values.append(value)
        self.heap_length += 1
        self.bubbleUp()
        return self

    def extractMax(self):
        max_element = self.values[0]
        end_element = self.values[self.heap_length - 1]

        if len(self.values) > 1:
            self.values[0] = end_element
            self.values[self.heap_length - 1] = max_element
            self.heap_length -= 1
            self.sinkDown()

        return max_element
    
    def build_max_heap(self, arr):
        for i in range(len(arr) - 1, -1, -1):
            self.max_heapify(arr, i)

        self.values = arr.copy()
        self.heap_length = len(self.values)


    def max_heapify(self, arr, i):
        element = arr[i]

        while i < len(arr):
            left_idx, right_idx = 2 * i + 1, 2 * i + 2
            left_child, right_child = float("-Inf"), float("-Inf")
            swap = None

            if left_idx < len(arr):
                left_child = arr[left_idx]
                if left_child > element:
                    swap = left_idx

            if right_idx < len(arr):
                right_child = arr[right_idx]
                if right_child > element and right_child > left_child:
                    swap = right_idx

            if swap is None:
                break

            arr[i] = arr[swap]
            arr[swap] = element
            i = swap

    

    def sort(self, arr):
        self.build_max_heap(arr)
        
        length = range(self.heap_length)
        for _ in length:
            self.extractMax()

        return ", ".join(map(str, self.values))

    
    def findParent(self, idx):
        return (idx - 1) // 2
    
    def bubbleUp(self):
        idx = len(self.values) - 1
        element = self.values[idx]

        while idx > 0:
            parent_idx = self.findParent(idx)
            parent = self.values[parent_idx]
            
            if element <= parent:
                break
            
            self.values[parent_idx] = element
            self.values[idx] = parent
            idx = parent_idx
    
    def sinkDown(self):
        i = 0
        length = self.heap_length
        element = self.values[0]

        while i < length:
            left_idx = 2 * i + 1
            right_idx = 2 * i + 2

            left_child = float("-Inf")
            right_child = float("-Inf")

            swap = None

            if left_idx < length:
                left_child = self.values[left_idx]
                if left_child > element:
                    swap = left_idx
            
            if right_idx < length:
                right_child = self.values[right_idx]
                if right_child > element and right_child > left_child:
                    swap = right_idx

            if swap is None:
                break

            self.values[i] = self.values[swap]
            self.values[swap] = element
            i = swap

        

random_numbers = random.sample(range(1, 10000), 1000)

max_heap = BinaryHeap()

print(max_heap.sort([50, 20, 10, 16, 30, 8, 15, 60]))
print(max_heap.sort(random_numbers))

max_heap.build_max_heap([10, 20, 15, 12, 40, 25, 18])
print(max_heap)

# max_heap.insert(60)
# print(max_heap)

# max_heap.extractMax()
# print(max_heap)

# max_heap.extractMax()
# print(max_heap)

# max_heap.extractMax()
# print(max_heap)

# max_heap.extractMax()
# print(max_heap)