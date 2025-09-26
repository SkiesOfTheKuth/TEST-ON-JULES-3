import asteval
from . import logic
import math

def create_evaluator():
    """
    Creates and configures an asteval interpreter with functions from the logic module.
    """
    interpreter = asteval.Interpreter()
    interpreter.symtable.update({
        # Basic operations
        'add': logic.add,
        'subtract': logic.subtract,
        'multiply': logic.multiply,
        'divide': logic.divide,

        # Advanced operations
        'power': logic.power,
        'sqrt': logic.sqrt,
        'abs': logic.absolute,
        'round': logic.round_number,

        # Trigonometric functions
        'sin': logic.sin,
        'cos': logic.cos,
        'tan': logic.tan,

        # Logarithmic functions
        'log': logic.log,
        'log10': logic.log10,

        # Factorial
        'factorial': logic.factorial,

        # Constants
        'pi': math.pi,
        'e': math.e,
    })
    return interpreter