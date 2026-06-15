"""Seed the knowledge base with ~25 industrial assets across 6 categories.

Each asset has: code, name, type, location, specs (dict), procedures (list of
{name, steps}). Maintenance history is seeded separately per asset.

Run via:  python seed.py   (or it is called automatically on first startup)
"""
import json
from db import db, init_db

# ---------------------------------------------------------------------------
# Asset registry. Codes follow a readable convention:
#   PMP=Pump  MTR=Motor  VLV=Valve  CMP=Compressor  GEN=Generator  HVC=HVAC
# ---------------------------------------------------------------------------
ASSETS = [
    # ---------------- PUMPS ----------------
    {
        "code": "PMP-4471", "name": "Cooling Water Pump A", "type": "Pump",
        "location": "Pump House Bay 2",
        "specs": {
            "flow_rate": "450 m3/h", "head": "65 m", "power": "75 kW",
            "voltage": "415 V", "rpm": "2950", "seal_type": "Mechanical, John Crane 5615",
            "max_temp": "90 C", "weight": "320 kg",
        },
        "procedures": [
            {"name": "Seal Replacement", "steps": [
                "Isolate and lock out the pump at the MCC.",
                "Close suction and discharge valves.",
                "Drain the casing and disconnect coupling guard.",
                "Remove the mechanical seal gland and old seal.",
                "Fit new seal, torque gland bolts to 25 Nm.",
                "Re-couple, restore valves, remove lockout, test run.",
            ]},
            {"name": "Bearing Lubrication", "steps": [
                "Wipe grease nipple clean.",
                "Apply 15 g of SKF LGEP 2 grease to each bearing.",
                "Run pump for 5 minutes and check for overheating.",
            ]},
        ],
    },
    {
        "code": "PMP-4472", "name": "Cooling Water Pump B", "type": "Pump",
        "location": "Pump House Bay 2",
        "specs": {"flow_rate": "450 m3/h", "head": "65 m", "power": "75 kW",
                  "voltage": "415 V", "rpm": "2950", "seal_type": "Mechanical, John Crane 5615",
                  "max_temp": "90 C", "weight": "320 kg"},
        "procedures": [
            {"name": "Seal Replacement", "steps": [
                "Isolate and lock out the pump.", "Close suction and discharge valves.",
                "Drain casing, remove seal gland, fit new seal.", "Restore and test run."]},
        ],
    },
    {
        "code": "PMP-3310", "name": "Boiler Feed Pump", "type": "Pump",
        "location": "Boiler Room",
        "specs": {"flow_rate": "120 m3/h", "head": "180 m", "power": "110 kW",
                  "voltage": "415 V", "rpm": "3550", "seal_type": "Cartridge seal",
                  "max_temp": "150 C", "weight": "480 kg"},
        "procedures": [
            {"name": "Pressure Test", "steps": [
                "Confirm boiler is offline and depressurised.",
                "Connect hydrostatic test rig to discharge.",
                "Pressurise to 1.5x working pressure, hold 30 minutes.",
                "Inspect for leaks, depressurise slowly."]},
        ],
    },
    {
        "code": "PMP-2205", "name": "Chemical Dosing Pump", "type": "Pump",
        "location": "Water Treatment Plant",
        "specs": {"flow_rate": "25 L/h", "head": "10 bar", "power": "0.75 kW",
                  "voltage": "230 V", "type_detail": "Diaphragm metering pump",
                  "material": "PVDF wetted parts"},
        "procedures": [
            {"name": "Diaphragm Replacement", "steps": [
                "Stop dosing and depressurise the line.",
                "Wear acid-resistant PPE.",
                "Remove pump head, replace diaphragm and O-rings.",
                "Reassemble and re-calibrate stroke."]},
        ],
    },
    {
        "code": "PMP-2206", "name": "Sump Drainage Pump", "type": "Pump",
        "location": "Basement Sump Pit",
        "specs": {"flow_rate": "60 m3/h", "head": "12 m", "power": "5.5 kW",
                  "voltage": "415 V", "type_detail": "Submersible", "ip_rating": "IP68"},
        "procedures": [
            {"name": "Float Switch Check", "steps": [
                "Manually lift float to confirm pump starts.",
                "Lower float to confirm pump stops.",
                "Clean debris from float and impeller intake."]},
        ],
    },

    # ---------------- MOTORS ----------------
    {
        "code": "MTR-1180", "name": "Conveyor Drive Motor 1", "type": "Motor",
        "location": "Production Line A",
        "specs": {"power": "37 kW", "voltage": "415 V", "rpm": "1475",
                  "frame": "IE3 200L", "insulation_class": "F", "bearing_de": "6312",
                  "bearing_nde": "6310"},
        "procedures": [
            {"name": "Insulation Resistance Test", "steps": [
                "Isolate and lock out the motor.",
                "Disconnect motor leads from the starter.",
                "Apply 500 V megger between windings and earth.",
                "Reading must be above 1 megohm; record value."]},
            {"name": "Bearing Replacement", "steps": [
                "Isolate motor and remove from base.",
                "Remove end shields and pull old bearings.",
                "Heat new bearings to 80 C and fit to shaft.",
                "Reassemble and check shaft end-float."]},
        ],
    },
    {
        "code": "MTR-1181", "name": "Conveyor Drive Motor 2", "type": "Motor",
        "location": "Production Line A",
        "specs": {"power": "37 kW", "voltage": "415 V", "rpm": "1475", "frame": "IE3 200L",
                  "insulation_class": "F"},
        "procedures": [
            {"name": "Insulation Resistance Test", "steps": [
                "Isolate and lock out.", "Apply 500 V megger to windings.",
                "Reading must exceed 1 megohm."]},
        ],
    },
    {
        "code": "MTR-2090", "name": "Exhaust Fan Motor", "type": "Motor",
        "location": "Workshop Roof",
        "specs": {"power": "11 kW", "voltage": "415 V", "rpm": "960", "frame": "IE2 160M",
                  "insulation_class": "F", "duty": "S1 continuous"},
        "procedures": [
            {"name": "Vibration Check", "steps": [
                "Mount accelerometer on bearing housing.",
                "Record velocity; alarm above 7.1 mm/s RMS.",
                "Balance or replace bearing if exceeded."]},
        ],
    },
    {
        "code": "MTR-2091", "name": "Mixer Agitator Motor", "type": "Motor",
        "location": "Mixing Tank 3",
        "specs": {"power": "22 kW", "voltage": "415 V", "rpm": "740",
                  "gearbox_ratio": "20:1", "frame": "IE3 180L"},
        "procedures": [
            {"name": "Gearbox Oil Change", "steps": [
                "Stop and lock out the agitator.",
                "Drain gearbox oil while warm.",
                "Refill with ISO VG 320 gear oil to sight glass.",
                "Run and check for leaks."]},
        ],
    },
    {
        "code": "MTR-3300", "name": "Crusher Main Motor", "type": "Motor",
        "location": "Crushing Plant",
        "specs": {"power": "160 kW", "voltage": "3300 V", "rpm": "990",
                  "frame": "IE3 315L", "insulation_class": "H", "cooling": "IC411"},
        "procedures": [
            {"name": "HV Winding Inspection", "steps": [
                "Obtain HV permit-to-work and earth the cables.",
                "Inspect winding overhangs for cracking.",
                "Perform polarisation index test.",
                "Record and clear permit."]},
        ],
    },

    # ---------------- VALVES ----------------
    {
        "code": "VLV-7001", "name": "Main Steam Isolation Valve", "type": "Valve",
        "location": "Steam Header",
        "specs": {"size": "DN200", "rating": "PN40", "type_detail": "Gate valve",
                  "actuator": "Electric, Rotork IQ", "material": "Cast steel WCB",
                  "max_temp": "400 C"},
        "procedures": [
            {"name": "Actuator Calibration", "steps": [
                "Set valve to manual.",
                "Drive to fully closed, set closed limit.",
                "Drive to fully open, set open limit.",
                "Verify torque trip settings and return to auto."]},
        ],
    },
    {
        "code": "VLV-7002", "name": "Cooling Water Control Valve", "type": "Valve",
        "location": "Pump House Bay 2",
        "specs": {"size": "DN150", "rating": "PN16", "type_detail": "Globe control valve",
                  "actuator": "Pneumatic diaphragm", "signal": "4-20 mA",
                  "fail_position": "Fail open"},
        "procedures": [
            {"name": "Positioner Check", "steps": [
                "Apply 4 mA, valve should be at 0 percent.",
                "Apply 20 mA, valve should be at 100 percent.",
                "Adjust zero and span on the positioner if off."]},
        ],
    },
    {
        "code": "VLV-7003", "name": "Pressure Relief Valve", "type": "Valve",
        "location": "Boiler Room",
        "specs": {"size": "DN80", "set_pressure": "12 bar", "type_detail": "Spring safety valve",
                  "material": "Stainless 316", "discharge": "Atmospheric vent"},
        "procedures": [
            {"name": "Set Pressure Test", "steps": [
                "Connect test rig to inlet.",
                "Raise pressure until valve lifts; record lift pressure.",
                "Confirm reseat within 10 percent.",
                "Apply test tag with date."]},
        ],
    },
    {
        "code": "VLV-7004", "name": "Gas Supply Shutoff Valve", "type": "Valve",
        "location": "Gas Skid",
        "specs": {"size": "DN100", "type_detail": "Ball valve, fire-safe",
                  "actuator": "Solenoid trip", "fail_position": "Fail closed"},
        "procedures": [
            {"name": "Trip Test", "steps": [
                "Notify control room before testing.",
                "De-energise solenoid; valve must slam shut within 2 seconds.",
                "Confirm leak-tight, reset and re-energise."]},
        ],
    },
    {
        "code": "VLV-7005", "name": "Effluent Discharge Valve", "type": "Valve",
        "location": "Water Treatment Plant",
        "specs": {"size": "DN250", "type_detail": "Butterfly valve",
                  "actuator": "Electric quarter-turn", "material": "Ductile iron, EPDM seat"},
        "procedures": [
            {"name": "Seat Leak Check", "steps": [
                "Close valve fully.",
                "Apply upstream pressure and inspect downstream for flow.",
                "Replace seat liner if leakage exceeds limit."]},
        ],
    },

    # ---------------- COMPRESSORS ----------------
    {
        "code": "CMP-5500", "name": "Plant Air Compressor 1", "type": "Compressor",
        "location": "Compressor Room",
        "specs": {"type_detail": "Rotary screw", "capacity": "15 m3/min", "pressure": "8 bar",
                  "power": "90 kW", "cooling": "Air-cooled", "oil_type": "Synthetic VDL 46"},
        "procedures": [
            {"name": "Air Filter Replacement", "steps": [
                "Stop compressor and depressurise.",
                "Open filter housing and remove old element.",
                "Fit new element and reset filter timer."]},
            {"name": "Oil Separator Change", "steps": [
                "Isolate and depressurise fully.",
                "Drain oil, remove separator element.",
                "Fit new separator and O-ring, refill oil.",
                "Run and check for oil carryover."]},
        ],
    },
    {
        "code": "CMP-5501", "name": "Plant Air Compressor 2", "type": "Compressor",
        "location": "Compressor Room",
        "specs": {"type_detail": "Rotary screw", "capacity": "15 m3/min", "pressure": "8 bar",
                  "power": "90 kW", "oil_type": "Synthetic VDL 46"},
        "procedures": [
            {"name": "Air Filter Replacement", "steps": [
                "Stop and depressurise.", "Replace filter element.", "Reset timer."]},
        ],
    },
    {
        "code": "CMP-5510", "name": "Instrument Air Compressor", "type": "Compressor",
        "location": "Compressor Room",
        "specs": {"type_detail": "Oil-free scroll", "capacity": "3 m3/min", "pressure": "7 bar",
                  "power": "22 kW", "dew_point": "-40 C"},
        "procedures": [
            {"name": "Dryer Desiccant Change", "steps": [
                "Switch dryer to bypass.",
                "Depressurise the offline tower.",
                "Replace desiccant beads.",
                "Return to service and verify dew point."]},
        ],
    },
    {
        "code": "CMP-5520", "name": "Refrigeration Compressor", "type": "Compressor",
        "location": "Cold Storage Plant",
        "specs": {"type_detail": "Reciprocating", "refrigerant": "R134a", "power": "55 kW",
                  "suction_pressure": "2 bar", "discharge_pressure": "14 bar"},
        "procedures": [
            {"name": "Refrigerant Leak Check", "steps": [
                "Use electronic halogen detector around joints.",
                "Check sight glass for bubbles.",
                "Top up refrigerant only if certified."]},
        ],
    },

    # ---------------- GENERATORS ----------------
    {
        "code": "GEN-9001", "name": "Emergency Diesel Generator 1", "type": "Generator",
        "location": "Generator House",
        "specs": {"power": "500 kVA", "voltage": "415 V", "fuel": "Diesel",
                  "engine": "Cummins QSX15", "rpm": "1500", "fuel_tank": "1000 L",
                  "cooling": "Radiator"},
        "procedures": [
            {"name": "Weekly No-Load Test", "steps": [
                "Confirm fuel level above 50 percent.",
                "Start generator, run off-load 10 minutes.",
                "Check oil pressure, coolant temp, battery charge.",
                "Stop and record readings in the logbook."]},
            {"name": "Load Bank Test", "steps": [
                "Connect load bank to output.",
                "Apply load in 25 percent steps to full load.",
                "Hold full load 2 hours, monitor temperatures.",
                "Reduce load gradually and cool down."]},
        ],
    },
    {
        "code": "GEN-9002", "name": "Emergency Diesel Generator 2", "type": "Generator",
        "location": "Generator House",
        "specs": {"power": "500 kVA", "voltage": "415 V", "fuel": "Diesel",
                  "engine": "Cummins QSX15", "rpm": "1500", "fuel_tank": "1000 L"},
        "procedures": [
            {"name": "Weekly No-Load Test", "steps": [
                "Check fuel and oil.", "Start and run off-load 10 minutes.",
                "Record readings and stop."]},
        ],
    },
    {
        "code": "GEN-9010", "name": "UPS Battery Bank", "type": "Generator",
        "location": "Control Room",
        "specs": {"type_detail": "VRLA battery bank", "capacity": "40 kVA", "autonomy": "30 min",
                  "cells": "240 x 2 V", "float_voltage": "2.27 V/cell"},
        "procedures": [
            {"name": "Battery Health Check", "steps": [
                "Measure each cell voltage on float.",
                "Record internal resistance with battery analyser.",
                "Flag any cell below 2.0 V for replacement."]},
        ],
    },

    # ---------------- HVAC ----------------
    {
        "code": "HVC-6001", "name": "Air Handling Unit 1", "type": "HVAC",
        "location": "Admin Block Roof",
        "specs": {"airflow": "8000 m3/h", "cooling_capacity": "45 kW", "filter": "G4 + F7",
                  "fan_power": "5.5 kW", "belt_type": "SPZ 1250"},
        "procedures": [
            {"name": "Filter Change", "steps": [
                "Switch AHU to off at the BMS.",
                "Open filter section, remove dirty filters.",
                "Fit new G4 pre-filter and F7 bag filter.",
                "Reset filter differential pressure alarm."]},
            {"name": "Belt Tension Check", "steps": [
                "Isolate fan.",
                "Press belt midspan; deflection should be 10 to 15 mm.",
                "Adjust motor slide rail to tension.",
                "Re-check alignment with straightedge."]},
        ],
    },
    {
        "code": "HVC-6002", "name": "Air Handling Unit 2", "type": "HVAC",
        "location": "Production Hall Roof",
        "specs": {"airflow": "12000 m3/h", "cooling_capacity": "70 kW", "filter": "G4 + F7",
                  "fan_power": "11 kW"},
        "procedures": [
            {"name": "Filter Change", "steps": [
                "Switch off at BMS.", "Replace pre and bag filters.",
                "Reset DP alarm."]},
        ],
    },
    {
        "code": "HVC-6010", "name": "Chiller Unit 1", "type": "HVAC",
        "location": "Chiller Yard",
        "specs": {"type_detail": "Water-cooled screw chiller", "cooling_capacity": "350 kW",
                  "refrigerant": "R134a", "power": "75 kW", "chilled_water_temp": "7 C flow"},
        "procedures": [
            {"name": "Condenser Tube Clean", "steps": [
                "Shut down chiller and isolate condenser water.",
                "Open end covers and brush-clean tubes.",
                "Flush, reassemble, and leak-check.",
                "Restart and verify approach temperature."]},
        ],
    },
    {
        "code": "HVC-6011", "name": "Cooling Tower 1", "type": "HVAC",
        "location": "Chiller Yard",
        "specs": {"type_detail": "Induced draft", "capacity": "400 kW", "fan_power": "7.5 kW",
                  "basin_volume": "5000 L", "fill_type": "Film fill"},
        "procedures": [
            {"name": "Basin Clean & Dose", "steps": [
                "Drain basin and remove sludge.",
                "Inspect fill and spray nozzles.",
                "Refill and dose biocide per water treatment plan."]},
        ],
    },

    # ---------------- HEAT EXCHANGERS ----------------
    {
        "code": "HEX-8001", "name": "Process Cooler Shell & Tube", "type": "Heat Exchanger",
        "location": "Process Area 1",
        "specs": {"type_detail": "Shell and tube, 1-2 pass", "duty": "1200 kW",
                  "tubes": "316 tubes, SS316", "shell_material": "Carbon steel",
                  "design_pressure": "10 bar", "design_temp": "180 C"},
        "procedures": [
            {"name": "Tube Bundle Clean", "steps": [
                "Isolate, drain and tag both sides.",
                "Remove channel covers and pull the tube bundle.",
                "Hydro-jet tubes and inspect for erosion.",
                "Pressure-test, reinstall bundle and gaskets."]},
            {"name": "Leak Test", "steps": [
                "Blank one side and fill with water.",
                "Pressurise to test pressure and hold 30 minutes.",
                "Inspect tube sheet for weeping; plug leaking tubes."]},
        ],
    },
    {
        "code": "HEX-8002", "name": "Lube Oil Cooler", "type": "Heat Exchanger",
        "location": "Compressor Room",
        "specs": {"type_detail": "Shell and tube", "duty": "150 kW",
                  "cooling_medium": "Cooling water", "design_pressure": "8 bar"},
        "procedures": [
            {"name": "Waterside Clean", "steps": [
                "Isolate cooling water side.",
                "Open end covers and rod out tubes.",
                "Flush and reassemble with new gaskets."]},
        ],
    },
    {
        "code": "HEX-8010", "name": "Plate Heat Exchanger 1", "type": "Heat Exchanger",
        "location": "Chiller Yard",
        "specs": {"type_detail": "Gasketed plate", "duty": "300 kW", "plates": "120",
                  "plate_material": "SS316", "gasket": "NBR", "design_pressure": "16 bar"},
        "procedures": [
            {"name": "Plate Pack Service", "steps": [
                "Record tightening dimension, then open the frame.",
                "Separate and inspect plates for scaling and cracks.",
                "Acid-clean plates, replace damaged gaskets.",
                "Reassemble to recorded tightening dimension."]},
        ],
    },
    {
        "code": "HEX-8011", "name": "Plate Heat Exchanger 2", "type": "Heat Exchanger",
        "location": "Chiller Yard",
        "specs": {"type_detail": "Gasketed plate", "duty": "300 kW", "plates": "120",
                  "plate_material": "SS316", "design_pressure": "16 bar"},
        "procedures": [
            {"name": "Plate Pack Service", "steps": [
                "Record tightening dimension and open frame.",
                "Clean plates and replace gaskets.",
                "Reassemble to recorded dimension."]},
        ],
    },

    # ---------------- TANKS & VESSELS ----------------
    {
        "code": "TNK-1000", "name": "Raw Water Storage Tank", "type": "Tank",
        "location": "Tank Farm",
        "specs": {"capacity": "200000 L", "material": "Carbon steel, epoxy lined",
                  "diameter": "8 m", "height": "5 m", "roof": "Fixed cone roof"},
        "procedures": [
            {"name": "Level Sensor Check", "steps": [
                "Compare radar level reading against sight glass.",
                "Calibrate transmitter zero and span if drifted.",
                "Test high-level alarm by simulation."]},
            {"name": "Internal Inspection", "steps": [
                "Issue confined-space and gas-test permits.",
                "Drain, ventilate and isolate the tank.",
                "Inspect lining and floor for corrosion, record thickness.",
                "Close out permit after re-entry."]},
        ],
    },
    {
        "code": "TNK-1001", "name": "Diesel Day Tank", "type": "Tank",
        "location": "Generator House",
        "specs": {"capacity": "5000 L", "material": "Carbon steel", "bund": "110 percent bunded",
                  "level_switch": "High and low float switches"},
        "procedures": [
            {"name": "Water Drain Check", "steps": [
                "Open the bottom drain slowly into a container.",
                "Drain off any settled water until clean diesel runs.",
                "Record quantity and dispose per waste procedure."]},
        ],
    },
    {
        "code": "TNK-2000", "name": "Air Receiver Vessel", "type": "Pressure Vessel",
        "location": "Compressor Room",
        "specs": {"capacity": "3000 L", "design_pressure": "11 bar", "material": "Carbon steel",
                  "safety_valve": "VLV-equivalent set 10.5 bar", "next_statutory": "2026-12-01"},
        "procedures": [
            {"name": "Drain & Inspect", "steps": [
                "Open the auto-drain and manual drain to remove condensate.",
                "Inspect internal surface via inspection opening.",
                "Verify safety valve test tag is current."]},
        ],
    },
    {
        "code": "TNK-2001", "name": "Chemical Mixing Tank", "type": "Tank",
        "location": "Water Treatment Plant",
        "specs": {"capacity": "8000 L", "material": "HDPE", "agitator": "MTR-2091 driven",
                  "ph_range": "2 to 12"},
        "procedures": [
            {"name": "Agitator & Seal Check", "steps": [
                "Confirm agitator runs without excessive vibration.",
                "Inspect top-entry seal for leakage.",
                "Check tank for cracks and UV degradation."]},
        ],
    },
    {
        "code": "TNK-2002", "name": "Condensate Receiver", "type": "Pressure Vessel",
        "location": "Boiler Room",
        "specs": {"capacity": "1500 L", "design_pressure": "6 bar", "material": "Carbon steel",
                  "temperature": "Up to 130 C"},
        "procedures": [
            {"name": "Steam Trap Check", "steps": [
                "Listen and thermal-scan each trap.",
                "Confirm condensate discharges without live steam loss.",
                "Replace failed traps."]},
        ],
    },

    # ---------------- ELECTRICAL (TRANSFORMERS / SWITCHGEAR) ----------------
    {
        "code": "TRF-100", "name": "Main Distribution Transformer", "type": "Transformer",
        "location": "Substation",
        "specs": {"rating": "1000 kVA", "primary": "11 kV", "secondary": "415 V",
                  "cooling": "ONAN, oil-filled", "vector_group": "Dyn11",
                  "oil_volume": "900 L"},
        "procedures": [
            {"name": "Oil Sample & DGA", "steps": [
                "De-energise and earth if sampling the tank.",
                "Draw oil sample from the bottom valve into clean bottle.",
                "Send for dissolved gas analysis.",
                "Check Buchholz relay and silica gel breather colour."]},
            {"name": "Thermography Scan", "steps": [
                "Scan bushings, cable boxes and tap changer under load.",
                "Flag any hotspot above 20 C over ambient delta.",
                "Record images and temperatures."]},
        ],
    },
    {
        "code": "TRF-101", "name": "Auxiliary Transformer", "type": "Transformer",
        "location": "Substation",
        "specs": {"rating": "315 kVA", "primary": "11 kV", "secondary": "415 V",
                  "cooling": "ONAN", "vector_group": "Dyn11"},
        "procedures": [
            {"name": "Breather & Oil Level Check", "steps": [
                "Check silica gel colour, replace if pink.",
                "Confirm oil level in the conservator sight glass."]},
        ],
    },
    {
        "code": "SWG-200", "name": "Main LV Switchboard", "type": "Switchgear",
        "location": "Substation",
        "specs": {"rating": "2000 A", "voltage": "415 V", "form": "Form 4b",
                  "breaker_type": "ACB, withdrawable", "fault_level": "50 kA"},
        "procedures": [
            {"name": "ACB Maintenance", "steps": [
                "Obtain permit, rack out the air circuit breaker.",
                "Clean contacts and check arc chutes.",
                "Lubricate mechanism and test trip via secondary injection.",
                "Rack in and restore."]},
            {"name": "Thermography Scan", "steps": [
                "Scan busbars and cable terminations under load.",
                "Flag hotspots and loose connections."]},
        ],
    },
    {
        "code": "SWG-201", "name": "Motor Control Centre 1", "type": "Switchgear",
        "location": "Production Line A",
        "specs": {"rating": "800 A", "voltage": "415 V", "starters": "DOL and VFD drawers",
                  "form": "Form 3b"},
        "procedures": [
            {"name": "Starter Drawer Check", "steps": [
                "Isolate the drawer and confirm dead.",
                "Inspect contactor contacts and overload settings.",
                "Tighten terminations to torque spec.",
                "Function-test start/stop."]},
        ],
    },
    {
        "code": "SWG-202", "name": "HV Ring Main Unit", "type": "Switchgear",
        "location": "Substation",
        "specs": {"rating": "630 A", "voltage": "11 kV", "type_detail": "SF6 insulated RMU",
                  "sf6_pressure": "Green zone"},
        "procedures": [
            {"name": "SF6 & Operation Check", "steps": [
                "Verify SF6 gauge is in the green zone.",
                "Check switch position indicators and interlocks.",
                "Confirm earth switch operation. HV permit required."]},
        ],
    },
]


# Maintenance history keyed by asset code. Dates are illustrative.
HISTORY = {
    "PMP-4471": [
        ("2026-01-12", "Mechanical seal replaced due to drip leak. Test run normal.", "R. Mehta"),
        ("2025-09-03", "Bearings re-greased during quarterly PM.", "A. Khan"),
        ("2025-05-20", "Coupling alignment corrected, vibration reduced.", "R. Mehta"),
    ],
    "PMP-3310": [
        ("2026-02-01", "Hydrostatic pressure test passed at 1.5x working pressure.", "S. Patel"),
    ],
    "MTR-1180": [
        ("2026-03-15", "Insulation resistance 120 megohm, healthy.", "A. Khan"),
        ("2025-11-10", "DE bearing 6312 replaced after vibration alarm.", "J. Lopez"),
    ],
    "MTR-3300": [
        ("2026-04-02", "HV winding inspection, polarisation index 2.4, acceptable.", "S. Patel"),
    ],
    "VLV-7003": [
        ("2026-01-30", "Safety valve set pressure tested, lifted at 12.1 bar, tagged.", "R. Mehta"),
    ],
    "CMP-5500": [
        ("2026-05-18", "Oil separator element changed, oil carryover resolved.", "A. Khan"),
        ("2025-12-22", "Air filter replaced during PM.", "J. Lopez"),
    ],
    "GEN-9001": [
        ("2026-06-08", "Weekly no-load test OK. Oil pressure 4.2 bar, coolant 78 C.", "S. Patel"),
        ("2026-03-01", "Annual load bank test passed at full load for 2 hours.", "R. Mehta"),
    ],
    "HEX-8001": [
        ("2026-04-25", "Tube bundle hydro-jetted, 2 tubes plugged, duty restored.", "J. Lopez"),
    ],
    "HEX-8010": [
        ("2026-05-12", "Plate pack opened and acid-cleaned, 4 gaskets replaced.", "A. Khan"),
    ],
    "TNK-2000": [
        ("2026-05-30", "Condensate drained, internal inspection clear. SV tag current.", "S. Patel"),
    ],
    "TRF-100": [
        ("2026-06-02", "Oil DGA sample sent. Silica gel breather replaced (pink).", "R. Mehta"),
        ("2026-02-18", "Thermography scan clear, max delta 8 C on LV bushing.", "S. Patel"),
    ],
    "SWG-200": [
        ("2026-04-10", "ACB maintenance done, contacts cleaned, trip test passed.", "J. Lopez"),
    ],
    "HVC-6001": [
        ("2026-05-05", "G4 and F7 filters replaced, DP alarm reset.", "A. Khan"),
        ("2026-02-14", "Fan belt re-tensioned, deflection set to 12 mm.", "J. Lopez"),
    ],
    "HVC-6010": [
        ("2026-04-20", "Condenser tubes cleaned, approach temp improved to 1.5 C.", "S. Patel"),
    ],
}


def seed():
    init_db()
    with db() as conn:
        existing = conn.execute("SELECT COUNT(*) AS n FROM assets").fetchone()["n"]
        if existing:
            print(f"Assets already seeded ({existing} rows). Skipping. "
                  f"Delete field_assistant.db to re-seed.")
            return

        for a in ASSETS:
            conn.execute(
                "INSERT INTO assets (code, name, type, location, specs, procedures) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (a["code"], a["name"], a["type"], a["location"],
                 json.dumps(a["specs"]), json.dumps(a["procedures"])),
            )

        for code, rows in HISTORY.items():
            for date, summary, tech in rows:
                conn.execute(
                    "INSERT INTO maintenance_history (asset_code, date, summary, technician) "
                    "VALUES (?, ?, ?, ?)",
                    (code, date, summary, tech),
                )

    print(f"Seeded {len(ASSETS)} assets and "
          f"{sum(len(v) for v in HISTORY.values())} history records.")


if __name__ == "__main__":
    seed()
