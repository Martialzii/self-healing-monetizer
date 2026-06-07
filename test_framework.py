import sys

def calculate_average(numbers):
    total = sum(numbers)
    return total / len(numbers)

print("Starting verification framework...")
data = [10, 20, 30, 40]
avg = calculate_average(data)
print(f"The average is: {avg}")