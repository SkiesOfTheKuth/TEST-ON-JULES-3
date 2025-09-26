import asteval
import logic

def create_evaluator():
    """
    Creates and configures an asteval interpreter with an expanded set of
    functions and constants from the logic module.
    """
    interpreter = asteval.Interpreter()

    # Update the symbol table with all public functions and constants from logic
    for name in dir(logic):
        if not name.startswith('_'):
            obj = getattr(logic, name)
            if callable(obj) or isinstance(obj, (int, float)):
                interpreter.symtable[name] = obj

    return interpreter