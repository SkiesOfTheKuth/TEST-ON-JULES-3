from flask import Flask, render_template, request, jsonify
from evaluator import create_evaluator

app = Flask(__name__)

# Initialize the asteval interpreter
asteval_interpreter = create_evaluator()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.get_json()
    expression = data.get('expression', '')

    if not expression:
        return jsonify({'error': 'Invalid expression'}), 400

    # asteval captures errors internally. We check the .error attribute.
    result = asteval_interpreter.eval(expression)
    if asteval_interpreter.error:
        error_message = asteval_interpreter.error[0].get_error()[1]
        asteval_interpreter.error = []  # Clear errors for the next request
        return jsonify({'error': error_message}), 400

    return jsonify({'result': result})

if __name__ == '__main__':
    app.run(debug=True)