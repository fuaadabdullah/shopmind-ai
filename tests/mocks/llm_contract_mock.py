"""Contract-validated LLM mock for E2E tests.

This mock provides realistic LLM responses that match the expected contract
for diagnostic ranking, while avoiding actual API calls and costs.
"""
import hashlib
import re
from typing import Any


class ContractValidatedLLMMock:
    """Mock LLM provider with contract validation.
    
    This mock returns realistic diagnostic rankings based on:
    - VIN hash (for determinism) 
    - OBD codes present in symptoms
    - Retrieved document content
    
    Responses are validated to ensure they match the expected structure:
    - Numbered list format (1. Cause, 2. Cause...)
    - Required sections: Why, Tests, Labor, Parts
    - Source citations [Source N]
    - Realistic content and formatting
    """
    
    # Template diagnoses based on common OBD codes
    DIAGNOSIS_TEMPLATES = {
        "P0171": {
            "cause": "Mass Air Flow (MAF) Sensor Failure",
            "why": "Code P0171 indicates a lean fuel mixture. MAF sensor failure is the most common cause, preventing proper air measurement. [Source 1] [Source 2]",
            "tests": ["MAF sensor voltage test", "Visual inspection for contamination", "Live data monitoring"],
            "labor": 0.5,
            "parts": ["MAF sensor", "Air filter"]
        },
        "P0420": {
            "cause": "Catalytic Converter Efficiency Below Threshold",
            "why": "P0420 indicates catalyst efficiency is below threshold. The converter substrate may be damaged or contaminated. [Source 1] [Source 3]",
            "tests": ["Downstream O2 sensor monitoring", "Substrate rattle test", "Backpressure measurement"],
            "labor": 3.0,
            "parts": ["Catalytic converter", "Oxygen sensors"]
        },
        "P0300": {
            "cause": "Random Multiple Cylinder Misfire",
            "why": "P0300 indicates misfires across multiple cylinders, suggesting systemic ignition or fuel delivery issue. [Source 2]",
            "tests": ["Compression test", "Fuel pressure test", "Ignition system inspection"],
            "labor": 2.5,
            "parts": ["Spark plugs", "Ignition coils", "Fuel filter"]
        },
        "P0455": {
            "cause": "EVAP System Large Leak Detected",
            "why": "P0455 indicates a large leak in the evaporative emission system. Most commonly a loose gas cap or cracked hose. [Source 1]",
            "tests": ["Visual inspection of gas cap", "Smoke test of EVAP system", "Purge valve test"],
            "labor": 1.5,
            "parts": ["Gas cap", "EVAP hoses", "Purge valve"]
        },
        "P0335": {
            "cause": "Crankshaft Position Sensor Circuit Malfunction",
            "why": "P0335 indicates crank position sensor failure. This prevents the ECU from determining engine timing. [Source 2]",
            "tests": ["Sensor resistance test", "Oscilloscope pattern analysis", "Air gap measurement"],
            "labor": 1.5,
            "parts": ["Crankshaft position sensor", "Sensor connector"]
        },
        "default": {
            "cause": "Multiple Potential Issues",
            "why": "Based on the symptoms and manual data, several interconnected systems may be involved. [Source 1] [Source 2]",
            "tests": ["Full system scan", "Visual inspection", "Component testing"],
            "labor": 2.0,
            "parts": ["Various components depending on test results"]
        }
    }
    
    # Secondary diagnoses (for ranking diversity)
    SECONDARY_DIAGNOSES = [
        {
            "cause": "Oxygen Sensor Degradation",
            "why": "Age and carbon buildup can degrade O2 sensor response time, affecting fuel trim. [Source 3]",
            "tests": ["O2 sensor response test", "Voltage cycling test", "Fuel trim analysis"],
            "labor": 1.0,
            "parts": ["Oxygen sensor", "Anti-seize compound"]
        },
        {
            "cause": "Vacuum Leak in Intake System",
            "why": "Unmetered air entering the intake causes lean conditions and rough running. [Source 2]",
            "tests": ["Smoke test", "Propane enrichment test", "Fuel trim monitoring"],
            "labor": 1.5,
            "parts": ["Intake gaskets", "Vacuum hoses"]
        },
        {
            "cause": "Fuel Injector Issues",
            "why": "Clogged or leaking injectors disrupt fuel delivery and cause performance issues. [Source 1]",
            "tests": ["Injector balance test", "Pressure drop test", "Cylinder contribution test"],
            "labor": 2.0,
            "parts": ["Fuel injectors", "Injector o-rings", "Fuel filter"]
        },
        {
            "cause": "Ignition System Failure",
            "why": "Worn spark plugs or failing coils prevent proper combustion. [Source 3]",
            "tests": ["Spark test", "Coil resistance test", "Plug gap inspection"],
            "labor": 1.5,
            "parts": ["Spark plugs", "Ignition coils"]
        },
        {
            "cause": "Throttle Body Issues",
            "why": "Carbon buildup or TPS malfunction affects idle and throttle response. [Source 2]",
            "tests": ["TPS voltage sweep", "Throttle body cleaning", "Idle relearn procedure"],
            "labor": 0.75,
            "parts": ["Throttle body cleaner", "TPS sensor"]
        }
    ]
    
    def __init__(self):
        """Initialize the mock LLM provider."""
        self.call_count = 0
    
    def generate(self, prompt: str) -> str:
        """Generate a mock LLM response matching expected contract.
        
        Args:
            prompt: Diagnostic prompt containing symptoms, OBD codes, docs
            
        Returns:
            Formatted diagnostic ranking as string
        """
        self.call_count += 1
        
        # Extract VIN, OBD codes, and symptoms from prompt
        vin = self._extract_vin(prompt)
        obd_codes = self._extract_obd_codes(prompt)
        
        # Determine primary diagnoses based on OBD codes
        primary_diagnoses = []
        for code in obd_codes:
            if code in self.DIAGNOSIS_TEMPLATES:
                primary_diagnoses.append(self.DIAGNOSIS_TEMPLATES[code])
        
        # If no matching codes, use default
        if not primary_diagnoses:
            primary_diagnoses = [self.DIAGNOSIS_TEMPLATES["default"]]
        
        # Use VIN hash to deterministically select secondary diagnoses
        vin_hash = int(hashlib.md5(vin.encode()).hexdigest(), 16) if vin else 0
        num_secondary = min(5 - len(primary_diagnoses), len(self.SECONDARY_DIAGNOSES))
        secondary_start = vin_hash % max(1, len(self.SECONDARY_DIAGNOSES) - num_secondary + 1)
        secondary_diagnoses = self.SECONDARY_DIAGNOSES[secondary_start:secondary_start + num_secondary]
        
        # Combine for full ranking
        all_diagnoses = primary_diagnoses + secondary_diagnoses
        all_diagnoses = all_diagnoses[:5]  # Top 5 only
        
        # Format response
        response_lines = []
        for i, diag in enumerate(all_diagnoses, 1):
            response_lines.append(f"{i}. {diag['cause']}")
            response_lines.append(f"   Why: {diag['why']}")
            response_lines.append(f"   Tests: {', '.join(diag['tests'])}")
            response_lines.append(f"   Labor: {diag['labor']} hours")
            response_lines.append(f"   Parts: {', '.join(diag['parts'])}")
            response_lines.append("")
        
        return "\n".join(response_lines)
    
    def _extract_vin(self, prompt: str) -> str:
        """Extract VIN from prompt."""
        match = re.search(r'Vehicle:\s*([A-Z0-9]{17})', prompt)
        return match.group(1) if match else ""
    
    def _extract_obd_codes(self, prompt: str) -> list[str]:
        """Extract OBD codes from prompt."""
        match = re.search(r'OBD Codes?:\s*([A-Z0-9,\s]+)', prompt)
        if not match:
            return []
        
        codes_text = match.group(1)
        # Extract all P/B/C/U codes
        codes = re.findall(r'[PBCU]\d{4}', codes_text)
        return codes
    
    def validate_response(self, response: str) -> tuple[bool, list[str]]:
        """Validate that response matches expected contract.
        
        Args:
            response: Generated response to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check for numbered list format
        if not re.search(r'^\d+\.\s+\w+', response, re.MULTILINE):
            errors.append("Response must start with numbered list (1. Cause)")
        
        # Check for required sections
        required_sections = ["Why:", "Tests:", "Labor:", "Parts:"]
        for section in required_sections:
            if section not in response:
                errors.append(f"Missing required section: {section}")
        
        # Check for source citations
        if not re.search(r'\[Source\s+\d+\]', response):
            errors.append("Response must include source citations [Source N]")
        
        # Check for reasonable length
        if len(response) < 100:
            errors.append("Response too short to be realistic")
        
        # Check that labor hours are present
        if not re.search(r'Labor:\s*[\d.]+\s*hours?', response, re.IGNORECASE):
            errors.append("Labor estimates must include numeric hours")
        
        return len(errors) == 0, errors


def create_mock_llm_provider() -> ContractValidatedLLMMock:
    """Factory function to create mock LLM provider.
    
    Returns:
        Configured ContractValidatedLLMMock instance
    """
    return ContractValidatedLLMMock()


if __name__ == "__main__":
    """Test the mock LLM provider."""
    mock = create_mock_llm_provider()
    
    # Test prompt
    test_prompt = """CUSTOMER INPUT:
Symptoms: car won't start, clicking sound when turning key
Vehicle: 1HGBH41JXMN109186
OBD Codes: P0335

KNOWLEDGE BASE (Retrieved Manual Data):
[Source 1: Manual]
Crankshaft position sensor failure...
[Source 2: TSB-001]
Common symptoms include no-start conditions...
"""
    
    response = mock.generate(test_prompt)
    print("=== Mock LLM Response ===")
    print(response)
    print("\n=== Validation ===")
    is_valid, errors = mock.validate_response(response)
    print(f"Valid: {is_valid}")
    if errors:
        print("Errors:")
        for error in errors:
            print(f"  - {error}")
