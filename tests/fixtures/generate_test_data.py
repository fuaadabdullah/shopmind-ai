"""Generate synthetic automotive diagnostic test data.

Creates realistic diagnostic scenarios for testing FAISS retrieval quality.
"""
from typing import Any


def get_test_diagnostic_scenarios() -> list[dict[str, Any]]:
    """Generate 20 realistic automotive diagnostic scenarios.
    
    Returns:
        List of diagnostic documents with fields:
        - cause: Primary diagnosis
        - description: Detailed explanation
        - tests: List of diagnostic tests
        - labor_hours: Estimated repair time
        - symptoms: Related symptoms (for embedding context)
        - obd_codes: Related OBD-II codes (for embedding context)
    """
    scenarios = [
        # Common Issues
        {
            "cause": "Mass Air Flow (MAF) Sensor Failure",
            "description": "The MAF sensor measures the amount of air entering the engine. When it fails, the ECU cannot properly calculate fuel delivery, leading to poor performance and fuel economy. Common causes include oil contamination from over-oiled air filters or sensor element degradation.",
            "tests": ["MAF sensor voltage test", "Scan for P0171/P0174", "Visual inspection for oil contamination", "Airflow meter reading"],
            "labor_hours": 0.5,
            "symptoms": ["rough idle", "hesitation on acceleration", "black smoke from exhaust", "check engine light"],
            "obd_codes": ["P0171", "P0174", "P0101", "P0102"]
        },
        {
            "cause": "Oxygen (O2) Sensor Degradation - Bank 1 Sensor 1",
            "description": "The upstream oxygen sensor monitors exhaust gas composition to optimize fuel trim. Degradation causes the ECU to operate in open-loop mode, increasing emissions and reducing fuel economy. Sensor response time slows with age and carbon buildup.",
            "tests": ["O2 sensor response time test", "Voltage cycling test", "Fuel trim analysis", "Exhaust backpressure test"],
            "labor_hours": 1.0,
            "symptoms": ["decreased fuel economy", "rough idle", "failed emissions test", "sluggish acceleration"],
            "obd_codes": ["P0131", "P0133", "P0171", "P0420"]
        },
        {
            "cause": "Catalytic Converter Efficiency Below Threshold",
            "description": "The catalytic converter reduces harmful emissions by converting NOx, CO, and HC into less harmful compounds. Efficiency loss occurs from substrate damage, contamination, or thermal degradation. Often caused by misfires or oil/coolant contamination.",
            "tests": ["Downstream O2 sensor monitoring", "Substrate rattle test", "Backpressure measurement", "Inlet/outlet temperature differential"],
            "labor_hours": 3.0,
            "symptoms": ["reduced power", "sulfur smell", "failed emissions", "rattling noise from underneath"],
            "obd_codes": ["P0420", "P0430", "P2096", "P2098"]
        },
        {
            "cause": "Evaporative Emission (EVAP) System Leak - Large",
            "description": "The EVAP system captures fuel vapors from the tank and routes them to the engine for combustion. Large leaks allow vapors to escape, triggering emissions warnings. Common causes include loose gas cap, cracked hoses, or faulty purge valve.",
            "tests": ["Smoke test of EVAP system", "Gas cap pressure test", "Purge valve actuation test", "Fuel tank pressure sensor reading"],
            "labor_hours": 1.5,
            "symptoms": ["fuel smell", "check engine light", "hissing sound near fuel tank", "difficulty starting when hot"],
            "obd_codes": ["P0455", "P0456", "P0457", "P0452"]
        },
        {
            "cause": "Ignition Coil Pack Failure - Cylinder Specific",
            "description": "Modern coil-on-plug systems use individual coils for each cylinder. Coil failure causes misfires, unburned fuel, and potential catalytic converter damage. Heat cycles and vibration are primary failure modes.",
            "tests": ["Coil resistance test", "Spark test", "Cylinder balance test", "Voltage supply check"],
            "labor_hours": 1.0,
            "symptoms": ["engine misfire", "rough running", "loss of power", "fuel smell from exhaust"],
            "obd_codes": ["P0300", "P0301", "P0302", "P0303", "P0304"]
        },
        {
            "cause": "Throttle Position Sensor (TPS) Malfunction",
            "description": "The TPS informs the ECU of throttle blade position for fuel and spark timing calculations. Sensor failure causes incorrect throttle angle reporting, leading to driveability issues. Carbon buildup or worn potentiometer tracks are common causes.",
            "tests": ["TPS voltage sweep test", "Throttle body cleaning", "Idle learn procedure", "Pedal position correlation test"],
            "labor_hours": 0.75,
            "symptoms": ["stalling", "surging at steady throttle", "poor acceleration response", "high idle"],
            "obd_codes": ["P0120", "P0121", "P0122", "P0123"]
        },
        
        # Complex Multi-System Issues
        {
            "cause": "Random Multiple Cylinder Misfire with Catalytic Converter Impact",
            "description": "Multiple cylinder misfires indicate systemic ignition or fuel delivery problems. Root causes include vacuum leaks, low fuel pressure, timing chain stretch, or carbon buildup on valves. Prolonged misfires damage the catalytic converter.",
            "tests": ["Compression test all cylinders", "Fuel pressure test", "Vacuum leak diagnosis", "Timing chain inspection", "Valve carbon inspection"],
            "labor_hours": 4.0,
            "symptoms": ["severe rough idle", "loss of power", "excessive fuel consumption", "loud exhaust noise", "catalyst overheating"],
            "obd_codes": ["P0300", "P0420", "P0171", "P0174"]
        },
        {
            "cause": "Crankshaft Position Sensor Intermittent Failure with Stalling",
            "description": "The crank sensor provides engine speed and position data for ignition timing. Intermittent failures cause sudden engine shutoff during driving. Heat-related failures are most common, often occurring after extended highway driving.",
            "tests": ["Crank sensor resistance test cold/hot", "Oscilloscope pattern analysis", "Air gap measurement", "Reluctor wheel inspection"],
            "labor_hours": 1.5,
            "symptoms": ["engine stalls while driving", "no start when hot", "intermittent no crank", "tachometer drops to zero"],
            "obd_codes": ["P0335", "P0336", "P0385", "P0016"]
        },
        
        # Electric/Hybrid Specific
        {
            "cause": "Hybrid Battery Pack Cell Imbalance",
            "description": "Hybrid battery packs contain multiple cells that must maintain voltage balance. Cell degradation causes imbalance, reducing pack capacity and triggering protective shutdowns. Hot climate operation accelerates degradation.",
            "tests": ["Battery module voltage test", "Capacity test", "Cooling fan operation check", "Temperature sensor validation"],
            "labor_hours": 6.0,
            "symptoms": ["reduced electric range", "reduced power in EV mode", "battery warning light", "excessive fan noise"],
            "obd_codes": ["P0A80", "P0A1F", "P3000", "P3006"]
        },
        {
            "cause": "High Voltage System Isolation Fault",
            "description": "Isolation faults indicate electrical leakage between the high voltage system and vehicle chassis. This is a critical safety issue that prevents vehicle operation. Causes include damaged cable insulation or moisture intrusion.",
            "tests": ["Insulation resistance test (500V megger)", "Cable harness visual inspection", "Connector seal inspection", "Inverter isolation test"],
            "labor_hours": 3.0,
            "symptoms": ["turtle mode (reduced power)", "high voltage system disabled", "won't go into READY mode", "warning messages on dash"],
            "obd_codes": ["P0AA6", "P0AFA", "P0A0F"]
        },
        
        # Transmission Issues
        {
            "cause": "Transmission Solenoid Pack Failure (Shift Quality)",
            "description": "Transmission solenoids control hydraulic pressure for gear changes. Solenoid failure causes harsh shifts, slipping, or gear ratio errors. Internal wear debris and fluid contamination are primary causes.",
            "tests": ["Solenoid resistance test", "Pressure control test", "Transmission fluid analysis", "Solenoid actuation test with scan tool"],
            "labor_hours": 4.5,
            "symptoms": ["harsh shifting", "slipping gears", "delayed engagement", "transmission warning light"],
            "obd_codes": ["P0750", "P0751", "P0753", "P0730"]
        },
        {
            "cause": "Transmission Fluid Temperature Sensor Circuit Malfunction",
            "description": "The fluid temperature sensor allows the TCM to adjust shift strategies and protect the transmission. Sensor failure can cause the transmission to operate in safe mode with restricted shifting.",
            "tests": ["Sensor resistance vs temperature", "Circuit continuity test", "TCM power supply check", "Fluid level and condition check"],
            "labor_hours": 1.0,
            "symptoms": ["transmission stays in low gear", "no upshifts", "transmission warning light", "harsh shifts when cold"],
            "obd_codes": ["P0710", "P0711", "P0712", "P0713"]
        },
        
        # Fuel System
        {
            "cause": "Fuel Pump Assembly Failure (Low Pressure)",
            "description": "The fuel pump delivers pressurized fuel to the injection system. Pump wear or electrical failure reduces pressure, causing fuel starvation under load. Contaminated fuel and running tank near empty accelerate failure.",
            "tests": ["Fuel pressure test at idle and WOT", "Fuel pump current draw test", "Fuel filter inspection", "Tank drop inspection"],
            "labor_hours": 2.5,
            "symptoms": ["stalling under acceleration", "won't start", "sputtering at high speed", "long crank time"],
            "obd_codes": ["P0087", "P0088", "P0230", "P0231"]
        },
        {
            "cause": "Fuel Injector Clogging - Multiple Cylinders",
            "description": "Fuel injectors spray atomized fuel into the combustion chamber. Carbon and varnish buildup restrict flow, causing lean conditions and misfires. Poor fuel quality and extended service intervals contribute to clogging.",
            "tests": ["Injector flow test", "Resistance test", "Cylinder contribution test", "Fuel pressure drop test"],
            "labor_hours": 3.0,
            "symptoms": ["rough idle", "hesitation", "poor fuel economy", "hard starting", "multiple misfires"],
            "obd_codes": ["P0171", "P0174", "P0300", "P0201", "P0202"]
        },
        
        # Cooling System
        {
            "cause": "Engine Coolant Temperature Sensor Circuit High",
            "description": "The ECT sensor provides critical temperature data for fuel trim, ignition timing, and cooling fan operation. High circuit voltage causes the ECU to think the engine is cold, enriching fuel mixture excessively.",
            "tests": ["Sensor resistance at various temperatures", "Circuit voltage test", "Ground circuit test", "Thermostat operation check"],
            "labor_hours": 0.5,
            "symptoms": ["poor fuel economy", "black smoke", "rough idle when warm", "cooling fan runs constantly"],
            "obd_codes": ["P0118", "P0119", "P0128"]
        },
        {
            "cause": "Thermostat Stuck Open (Slow Warmup)",
            "description": "The thermostat regulates coolant flow to maintain optimal operating temperature. A stuck-open thermostat prevents the engine from reaching proper temperature, reducing efficiency and increasing wear.",
            "tests": ["Coolant temperature monitoring during warmup", "Thermostat removal inspection", "IR temperature gun scan", "Block heater test"],
            "labor_hours": 1.0,
            "symptoms": ["long warmup time", "heater barely warm", "reduced fuel economy", "temperature gauge below normal"],
            "obd_codes": ["P0128", "P0597"]
        },
        
        # Electrical
        {
            "cause": "Alternator Voltage Regulator Failure (Overcharging)",
            "description": "The voltage regulator maintains charging system output at 13.5-14.5V. Regulator failure causes overcharging, boiling battery electrolyte and damaging electrical components.",
            "tests": ["Charging system voltage test", "Ripple voltage test", "Diode test", "Load test"],
            "labor_hours": 1.5,
            "symptoms": ["battery boiling", "dimming lights when accelerating", "electrical component failures", "battery warning light"],
            "obd_codes": ["P0562", "P0563", "P2503"]
        },
        {
            "cause": "Battery Sulfation (Reduced Capacity)",
            "description": "Lead-acid batteries develop lead sulfate crystals over time, reducing capacity and cold cranking amps. Repeated deep discharges and undercharging accelerate sulfation.",
            "tests": ["Load test", "Specific gravity test", "CCA test", "Voltage drop test"],
            "labor_hours": 0.25,
            "symptoms": ["slow cranking", "won't start in cold weather", "battery light on", "accessories dim when starting"],
            "obd_codes": ["P0560", "P0561", "P0562"]
        },
        
        # Air Intake
        {
            "cause": "Air Intake System Leak After MAF Sensor",
            "description": "Unmetered air entering after the MAF sensor causes the ECU to run lean, as it cannot account for the additional airflow. Common leak points include intake manifold gaskets, throttle body gasket, and vacuum hoses.",
            "tests": ["Smoke test", "Fuel trim analysis", "Propane enrichment test", "Visual inspection of gaskets and hoses"],
            "labor_hours": 2.0,
            "symptoms": ["rough idle", "stalling", "hesitation", "lean codes", "whistling noise from engine bay"],
            "obd_codes": ["P0171", "P0174", "P0507", "P2177"]
        },
        {
            "cause": "Turbocharger Wastegate Actuator Stuck Closed",
            "description": "The wastegate controls boost pressure by diverting exhaust gases. A stuck-closed wastegate causes overboost, triggering limp mode to protect the engine. Carbon buildup and seized linkage are common causes.",
            "tests": ["Boost pressure test", "Wastegate actuation test", "Vacuum/boost leak test", "Turbo shaft play inspection"],
            "labor_hours": 3.0,
            "symptoms": ["reduced power", "limp mode", "excessive boost pressure", "loud whistling under load"],
            "obd_codes": ["P0234", "P0235", "P0299", "P2563"]
        },
        
        # Exhaust/Emissions
        {
            "cause": "EGR Valve Carbon Buildup and Sticking",
            "description": "The EGR valve recirculates exhaust gases to reduce NOx emissions. Carbon deposits prevent proper sealing, causing rough idle or preventing opening, triggering emissions codes.",
            "tests": ["EGR valve actuation test", "EGR passage inspection", "Intake manifold pressure test", "EGR cleaning"],
            "labor_hours": 2.0,
            "symptoms": ["rough idle", "stalling", "surging at light throttle", "failed emissions test"],
            "obd_codes": ["P0401", "P0402", "P0403", "P0404"]
        }
    ]
    
    return scenarios


if __name__ == "__main__":
    """Print test scenarios for validation."""
    scenarios = get_test_diagnostic_scenarios()
    print(f"Generated {len(scenarios)} test diagnostic scenarios\n")
    
    for i, scenario in enumerate(scenarios[:3], 1):
        print(f"=== Scenario {i}: {scenario['cause']} ===")
        print(f"Description: {scenario['description'][:100]}...")
        print(f"Tests: {len(scenario['tests'])}")
        print(f"Labor Hours: {scenario['labor_hours']}")
        print(f"Symptoms: {', '.join(scenario['symptoms'][:3])}")
        print(f"OBD Codes: {', '.join(scenario['obd_codes'])}")
        print()
