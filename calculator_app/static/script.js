const AUTH_HEADER = (() => {
  const token = window.localStorage.getItem('calculator_api_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
})();

document.addEventListener('DOMContentLoaded', () => {
  const display = document.getElementById('display');
  const buttons = document.querySelector('.buttons');
  const message = document.getElementById('message');

  let currentExpression = '';
  let isResultDisplayed = false;

  buttons.addEventListener('click', async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement)) return;

    const { value } = target.dataset;
    if (!value) return;

    switch (value) {
      case 'C':
        reset();
        break;
      case '=':
        if (currentExpression === '') return;
        await calculate(currentExpression);
        break;
      default:
        if (isResultDisplayed && !['+', '-', '*', '/'].includes(value)) {
          currentExpression = '';
        }
        isResultDisplayed = false;
        currentExpression += value;
        display.textContent = currentExpression;
        break;
    }
  });

  function reset() {
    currentExpression = '';
    isResultDisplayed = false;
    display.textContent = '0';
    updateMessage('Cleared expression.');
  }

  async function calculate(expression) {
    try {
      const response = await fetch('/calculate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...AUTH_HEADER,
        },
        body: JSON.stringify({ expression }),
      });

      const data = await response.json();

      if (response.ok) {
        display.textContent = data.result;
        currentExpression = String(data.result);
        isResultDisplayed = true;
        updateMessage('Calculation complete.');
        return;
      }

      display.textContent = 'Error';
      currentExpression = '';
      updateMessage(data.error ?? 'Unable to calculate expression.');
    } catch (error) {
      display.textContent = 'Error';
      currentExpression = '';
      updateMessage('Network error. Please try again.');
    }
  }

  function updateMessage(text) {
    if (message) {
      message.textContent = text;
    }
  }
});
