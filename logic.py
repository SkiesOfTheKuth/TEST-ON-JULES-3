def add(x, y):
    """This function adds two numbers"""
    return x + y

def subtract(x, y):
    """This function subtracts two numbers"""
    return x - y

def multiply(x, y):
    """This function multiplies two numbers"""
    return x * y

def divide(x, y):
    """This function divides two numbers"""
    if y == 0:
        raise ValueError("Cannot divide by zero")
    return x / y

def power(x, y):
    """This function raises x to the power of y"""
    return x ** y

def sqrt(x):
    """This function finds the square root of a number"""
    if x < 0:
        raise ValueError("Cannot take the square root of a negative number")
    return x ** 0.5