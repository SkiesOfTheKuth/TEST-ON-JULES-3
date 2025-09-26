import asteval
import logic

def create_evaluator():
    """
    Creates and configures an asteval interpreter with functions from the logic module.
    """
    interpreter = asteval.Interpreter()
    interpreter.symtable.update({
        'add': logic.add,
        'subtract': logic.subtract,
        'multiply': logic.multiply,
        'divide': logic.divide,
        'power': logic.power,
        'sqrt': logic.sqrt,
        'sin': logic.sin,
        'cos': logic.cos,
        'tan': logic.tan,
        'log': logic.log,
        'log10': logic.log10,
        'factorial': logic.factorial,
    })
    return interpreter