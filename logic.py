import math

class Calculator:
    def power(self, x, y):
        """This function raises x to the power of y"""
        return x ** y

    def sqrt(self, x):
        """This function finds the square root of a number"""
        if x < 0:
            raise ValueError("Cannot take the square root of a negative number")
        return math.sqrt(x)

    def sin(self, x):
        """This function finds the sine of a number in degrees"""
        return math.sin(math.radians(x))

    def cos(self, x):
        """This function finds the cosine of a number in degrees"""
        return math.cos(math.radians(x))

    def tan(self, x):
        """This function finds the tangent of a number in degrees"""
        return math.tan(math.radians(x))

    def asin(self, x):
        """This function finds the arc sine of a number in degrees"""
        if not -1 <= x <= 1:
            raise ValueError("Input for asin must be between -1 and 1")
        return math.degrees(math.asin(x))

    def acos(self, x):
        """This function finds the arc cosine of a number in degrees"""
        if not -1 <= x <= 1:
            raise ValueError("Input for acos must be between -1 and 1")
        return math.degrees(math.acos(x))

    def atan(self, x):
        """This function finds the arc tangent of a number in degrees"""
        return math.degrees(math.atan(x))

    def log(self, x):
        """This function finds the natural logarithm of a number"""
        if x <= 0:
            raise ValueError("Cannot take the logarithm of a non-positive number")
        return math.log(x)

    def log10(self, x):
        """This function finds the base-10 logarithm of a number"""
        if x <= 0:
            raise ValueError("Cannot take the logarithm of a non-positive number")
        return math.log10(x)

    def factorial(self, x):
        """This function finds the factorial of a number"""
        if not isinstance(x, int) or x < 0:
            raise ValueError("Factorial is only defined for non-negative integers")
        return math.factorial(x)

    def percentage(self, x, y):
        """This function calculates x percent of y"""
        return (x * y) / 100

    def mod(self, x, y):
        """This function finds the remainder of x divided by y"""
        return x % y

    @property
    def pi(self):
        """This function returns the value of pi"""
        return math.pi

    @property
    def e(self):
        """This function returns the value of e"""
        return math.e