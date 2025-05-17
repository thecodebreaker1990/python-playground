#File Objects

with open("assets/test.txt", "r") as rf:
    with open("assets/test_copy.txt", "w") as wf:
        for line in rf:
            wf.write(line)