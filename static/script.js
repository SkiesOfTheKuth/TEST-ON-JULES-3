document.addEventListener('DOMContentLoaded', () => {
    const display = document.getElementById('display');
    const buttonsGrid = document.querySelector('.buttons-grid');
    const historyPanel = document.getElementById('history-panel');
    const clearHistoryBtn = document.getElementById('clear-history-btn');

    // --- State Management ---
    const state = {
        currentInput: '0',
        isResultDisplayed: false,
        memory: 0,
        history: [],
    };

    // --- UI Rendering ---
    const updateDisplay = () => {
        // Replace backend operators with user-friendly symbols
        const formattedInput = state.currentInput
            .replace(/\*/g, '×')
            .replace(/\//g, '÷')
            .replace(/\*\*/g, '^')
            .replace(/math./g, ''); // Clean up any function prefixes if they appear
        display.value = formattedInput;
    };

    const updateHistory = () => {
        historyPanel.innerHTML = '';
        state.history.forEach(item => {
            const historyItem = document.createElement('div');
            historyItem.classList.add('history-item');
            historyItem.textContent = `${item.expression} = ${item.result}`;
            historyItem.addEventListener('click', () => {
                // Clicking a history item puts the result back into the display
                state.currentInput = String(item.result);
                state.isResultDisplayed = true;
                updateDisplay();
            });
            historyPanel.appendChild(historyItem);
        });
    };

    // --- Core Logic ---
    const handleButtonPress = (value) => {
        if (value === 'C') {
            handleClear();
        } else if (value === 'Backspace') {
            handleBackspace();
        } else if (value === '=') {
            handleEquals();
        } else if (value.startsWith('M')) {
            handleMemory(value);
        } else {
            handleInput(value);
        }
        updateDisplay();
    };

    const handleMemory = (value) => {
        const currentNumber = parseFloat(state.currentInput);

        if (isNaN(currentNumber) && value !== 'MC' && value !== 'MR') {
            // Don't do M+ or M- if the display is not a number
            return;
        }

        switch (value) {
            case 'MC':
                state.memory = 0;
                break;
            case 'M+':
                state.memory += currentNumber;
                break;
            case 'M-':
                state.memory -= currentNumber;
                break;
            case 'MR':
                state.currentInput = String(state.memory);
                state.isResultDisplayed = true; // Treat memory recall like a result
                break;
        }
    };

    const handleClear = () => {
        state.currentInput = '0';
        state.isResultDisplayed = false;
    };

    const handleBackspace = () => {
        if (state.isResultDisplayed) {
            handleClear();
            return;
        }
        if (state.currentInput.length > 1) {
            state.currentInput = state.currentInput.slice(0, -1);
        } else {
            state.currentInput = '0';
        }
    };

    const handleEquals = () => {
        if (state.currentInput && !state.isResultDisplayed) {
            calculate(state.currentInput);
        }
    };

    const handleInput = (value) => {
        const isOperator = ['+', '-', '*', '/', '**'].includes(value);

        if (state.isResultDisplayed) {
            if (isOperator) {
                // Continue calculation with the previous result
                state.currentInput += value;
            } else {
                // Start a new calculation
                state.currentInput = value;
            }
            state.isResultDisplayed = false;
        } else {
            if (state.currentInput === '0' && value !== '.') {
                state.currentInput = value;
            } else {
                state.currentInput += value;
            }
        }
    };

    const calculate = async (expression) => {
        // Sanitize expression for the backend
        const sanitizedExpression = expression
            .replace(/×/g, '*')
            .replace(/÷/g, '/')
            .replace(/−/g, '-')
            .replace(/\^/g, '**');

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
                const newHistoryItem = { expression: sanitizedExpression, result: data.result };
                state.history.unshift(newHistoryItem); // Add to the beginning of the array
                if (state.history.length > 20) {
                    state.history.pop(); // Keep history to a reasonable size
                }
                updateHistory();

                state.currentInput = String(data.result);
                state.isResultDisplayed = true;
            } else {
                state.currentInput = data.error || 'Error';
                state.isResultDisplayed = true;
            }
        } catch (error) {
            state.currentInput = 'Network Error';
            state.isResultDisplayed = true;
        }
        updateDisplay();
    };

    // --- Event Listeners ---
    buttonsGrid.addEventListener('click', (e) => {
        if (e.target.matches('.btn')) {
            e.preventDefault();
            const value = e.target.dataset.value;
            handleButtonPress(value);
        }
    });

    clearHistoryBtn.addEventListener('click', () => {
        state.history = [];
        updateHistory();
    });

    document.addEventListener('keydown', (e) => {
        e.preventDefault();
        const key = e.key;
        let value = '';

        if (key >= '0' && key <= '9') value = key;
        else if (key === '.') value = '.';
        else if (key === '+') value = '+';
        else if (key === '-') value = '-';
        else if (key === '*') value = '*';
        else if (key === '/') value = '/';
        else if (key === '^') value = '**';
        else if (key === '(') value = '(';
        else if (key === ')') value = ')';
        else if (key === 'Enter' || key === '=') value = '=';
        else if (key === 'Backspace') value = 'Backspace';
        else if (key.toLowerCase() === 'c') value = 'C';

        if (value) {
            handleButtonPress(value);
        }
    });

    // --- Initial Load ---
    updateDisplay();
});