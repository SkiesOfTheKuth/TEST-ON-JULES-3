import math

def power(x, y):
    """This function raises x to the power of y"""
    return x ** y

def sqrt(x):
    """This function finds the square root of a number"""
    if x < 0:
        raise ValueError("Cannot take the square root of a negative number")
    return math.sqrt(x)

def sin(x):
    """This function finds the sine of a number"""
    return math.sin(math.radians(x))

def cos(x):
    """This function finds the cosine of a number"""
    return math.cos(math.radians(x))

def tan(x):
    """This function finds the tangent of a number"""
    return math.tan(math.radians(x))

def log(x):
    """This function finds the natural logarithm of a number"""
    if x <= 0:
        raise ValueError("Cannot take the logarithm of a non-positive number")
    return math.log(x)

def log10(x):
    """This function finds the base-10 logarithm of a number"""
    if x <= 0:
        raise ValueError("Cannot take the logarithm of a non-positive number")
    return math.log10(x)

def factorial(x):
    """This function finds the factorial of a number"""
    if not isinstance(x, int) or x < 0:
        raise ValueError("Factorial is only defined for non-negative integers")
    return math.factorial(x)

def percentage(x, y):
    """This function calculates x percent of y"""
    return (x * y) / 100