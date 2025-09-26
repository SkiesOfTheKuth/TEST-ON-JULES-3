from flask import Flask, render_template, request, jsonify
import asteval
import logic

app = Flask(__name__)

# Initialize the asteval interpreter
asteval_interpreter = asteval.Interpreter()
asteval_interpreter.symtable.update({
    'sqrt': logic.sqrt,
    'power': logic.power,
    'sin': logic.sin,
    'cos': logic.cos,
    'tan': logic.tan,
    'log': logic.log,
    'log10': logic.log10,
    'factorial': logic.factorial,
    'percentage': logic.percentage,
})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.get_json()
    expression = data.get('expression', '')

    if not expression:
        return jsonify({'error': 'Invalid expression'}), 400

    try:
        # Clear previous errors, as the interpreter is reused
        asteval_interpreter.error = []
        result = asteval_interpreter.eval(expression)

        # Check if any errors occurred during evaluation
        if asteval_interpreter.error:
            # Get the first error and format it
            error_message = asteval_interpreter.error[0].get_error()[1]
            return jsonify({'error': error_message}), 400

        return jsonify({'result': result})
    except Exception as e:
        # This will catch other unexpected errors
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)