async function runDiagnosis() {
  const vin = document.getElementById('vin').value;
  const codes = document.getElementById('codes').value;
  const symptoms = document.getElementById('symptoms').value;
  const output = document.getElementById('output');
  const button = document.querySelector('button');

  if (!symptoms) {
    output.textContent = 'Please describe the issue.';
    return;
  }

  button.disabled = true;
  button.textContent = 'Diagnosing...';
  output.textContent = 'Processing...';

  try {
    const response = await fetch('/diagnose', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        vin: vin,
        obdcodes: codes,
        symptoms: symptoms
      })
    });

    const data = await response.json();
    output.textContent = data.result || 'No results found.';
  } catch (error) {
    output.textContent = 'Error: ' + error.message;
  } finally {
    button.disabled = false;
    button.textContent = 'Diagnose';
  }
}
