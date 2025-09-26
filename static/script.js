document.addEventListener('DOMContentLoaded', () => {
    const display = document.getElementById('display');
    const buttonsGrid = document.querySelector('.buttons-grid');

    let currentInput = '0';
    let isResultDisplayed = false;

    const updateDisplay = () => {
        // Replace operators for better readability
        const formattedInput = currentInput
            .replace(/\*/g, '×')
            .replace(/\//g, '÷')
            .replace(/\*\*/g, '^');
        display.value = formattedInput;
    };

    const handleButtonPress = (value) => {
        if (value === 'C') {
            currentInput = '0';
            isResultDisplayed = false;
        } else if (value === 'Backspace') {
            if (currentInput.length > 1) {
                currentInput = currentInput.slice(0, -1);
            } else {
                currentInput = '0';
            }
            isResultDisplayed = false;
        } else if (value === '=') {
            if (currentInput) {
                calculate(currentInput);
            }
        } else {
            if (isResultDisplayed) {
                // If the previous result is on display, decide what to do
                const isOperator = ['+', '-', '*', '/', '**', '^'].includes(value);
                if (isOperator) {
                    // Start new calculation with previous result
                } else {
                    // Start a fresh calculation
                    currentInput = '';
                }
                isResultDisplayed = false;
            }

            if (currentInput === '0' && value !== '.') {
                currentInput = value;
            } else {
                currentInput += value;
            }
        }
        updateDisplay();
    };

    buttonsGrid.addEventListener('click', (e) => {
        if (e.target.matches('.btn')) {
            e.preventDefault();
            const value = e.target.dataset.value;
            handleButtonPress(value);
        }
    });

    const calculate = async (expression) => {
        // Sanitize expression for backend
        const sanitizedExpression = expression.replace(/×/g, '*').replace(/÷/g, '/').replace(/−/g, '-').replace(/\^/g, '**');

        try {
            const response = await fetch('/calculate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ expression: sanitizedExpression }),
            });

            const data = await response.json();

            if (response.ok) {
                currentInput = String(data.result);
                isResultDisplayed = true;
            } else {
                currentInput = data.error || 'Error';
                isResultDisplayed = true;
            }
        } catch (error) {
            currentInput = 'Network Error';
            isResultDisplayed = true;
        }
        updateDisplay();
    };

    // --- Keyboard Support ---
    document.addEventListener('keydown', (e) => {
        e.preventDefault();
        const key = e.key;
        let value = '';

        if (key >= '0' && key <= '9') {
            value = key;
        } else if (key === '.') {
            value = '.';
        } else if (key === '+') {
            value = '+';
        } else if (key === '-') {
            value = '-';
        } else if (key === '*') {
            value = '*';
        } else if (key === '/') {
            value = '/';
        } else if (key === '^') {
            value = '**';
        } else if (key === '(') {
            value = '(';
        } else if (key === ')') {
            value = ')';
        } else if (key === 'Enter' || key === '=') {
            value = '=';
        } else if (key === 'Backspace') {
            value = 'Backspace';
        } else if (key.toLowerCase() === 'c') {
            value = 'C';
        }

        if (value) {
            handleButtonPress(value);
        }
    });

    // Initial display update
    updateDisplay();
});