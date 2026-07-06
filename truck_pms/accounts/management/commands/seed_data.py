from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from pms.models import TaskCategory, TaskTemplate, PMSchedule
from trucks.models import Truck
from contractors.models import Contractor

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed initial data for the Truck PMS system'

    def handle(self, *args, **options):
        self.stdout.write('Seeding data...')

        # Create superuser
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@truckpms.local',
                password='admin123',
                role=User.Role.SUPER_ADMIN,
                first_name='System',
                last_name='Admin',
            )
            self.stdout.write('  Created superuser: admin / admin123')

        # Create sample users
        users_data = [
            ('miguel', 'Miguel', 'Santos', User.Role.ADMIN, 'General'),
            ('juan', 'Juan', 'dela Cruz', User.Role.STAFF, 'Dispatch'),
            ('pedro', 'Pedro', 'Reyes', User.Role.MECHANIC, 'Engine & Transmission'),
            ('andres', 'Andres', 'Bonifacio', User.Role.MECHANIC, 'Brakes & Suspension'),
            ('contractor1', 'Jose', 'Rizal', User.Role.CONTRACTOR, 'Electrical'),
        ]
        for username, fn, ln, role, spec in users_data:
            if not User.objects.filter(username=username).exists():
                User.objects.create_user(
                    username=username,
                    password='password123',
                    first_name=fn,
                    last_name=ln,
                    role=role,
                    specialization=spec,
                )
                self.stdout.write(f'  Created user: {username} / password123')

        # Create task categories
        categories = [
            ('ENGINE_PM', 'Engine PM', 'Preventive maintenance for engine systems'),
            ('TRANSMISSION', 'Transmission', 'Transmission and drivetrain maintenance'),
            ('BRAKES', 'Brakes', 'Brake system inspection and repair'),
            ('TIRES', 'Tires', 'Tire inspection, rotation, and replacement'),
            ('BATTERY_ELECTRICAL', 'Battery & Electrical', 'Battery and electrical system checks'),
            ('CHASSIS', 'Chassis', 'Chassis and frame lubrication and inspection'),
            ('FUEL_SYSTEM', 'Fuel System', 'Fuel system filters and components'),
            ('TANK_INTEGRITY', 'Tank Integrity', 'Tanker tank inspections and testing'),
            ('VALVES', 'Valves', 'Internal and external valve service'),
            ('VAPOR_RECOVERY', 'Vapor Recovery', 'Vapor recovery system maintenance'),
            ('HOSES_COUPLINGS', 'Hoses & Couplings', 'Hose and coupling inspections'),
            ('PUMP_SYSTEM', 'Pump System', 'Pump system maintenance and repair'),
            ('METERING', 'Metering', 'Meter calibration and accuracy testing'),
            ('GROUNDING', 'Grounding', 'Grounding cable and continuity checks'),
            ('SAFETY', 'Safety Equipment', 'Fire extinguisher, emergency shutdown, placards'),
            ('LIGHTING', 'Lighting', 'All lighting components'),
            ('WIRING', 'Wiring & Sensors', 'Wiring harness and sensor repairs'),
            ('SUSPENSION', 'Suspension', 'Suspension and steering components'),
            ('EXHAUST', 'Exhaust', 'Exhaust system and DPF maintenance'),
            ('HVAC', 'HVAC', 'Air conditioning and heating system'),
            ('HYDRAULICS', 'Hydraulics', 'Hydraulic system maintenance'),
            ('BODY', 'Body & Chassis', 'Body repair, welding, and painting'),
            ('INSPECTION', 'Inspection & Compliance', 'LTO, insurance, and compliance inspections'),
        ]
        cat_objs = {}
        for code, name, desc in categories:
            cat, created = TaskCategory.objects.get_or_create(
                name=name, defaults={'description': desc}
            )
            cat_objs[code] = cat
            if created:
                self.stdout.write(f'  Created category: {name}')

        # Create task templates
        templates = [
            # ── ENGINE PM ──
            ('ENGINE_PM', 'Change Engine Oil', 'MILEAGE', 5000, False, '', 1.0),
            ('ENGINE_PM', 'Replace Oil Filter', 'MILEAGE', 5000, False, '', 0.5),
            ('ENGINE_PM', 'Replace Fuel Filter', 'MILEAGE', 10000, False, '', 0.5),
            ('ENGINE_PM', 'Replace Air Filter', 'MILEAGE', 10000, False, '', 0.3),
            ('ENGINE_PM', 'Coolant Check & Top-up', 'MILEAGE', 10000, False, '', 0.3),
            ('ENGINE_PM', 'Belt Inspection', 'VISUAL', None, False, '', 0.2),
            ('ENGINE_PM', 'Turbocharger Inspection', 'MILEAGE', 20000, False, '', 0.5),
            ('ENGINE_PM', 'Fan Belt Tension Check', 'MILEAGE', 5000, False, '', 0.2),
            ('ENGINE_PM', 'Air Compressor Service', 'MILEAGE', 20000, False, '', 0.5),
            ('ENGINE_PM', 'Thermostat Check', 'MILEAGE', 30000, False, '', 0.3),
            ('ENGINE_PM', 'Engine Mount Inspection', 'MILEAGE', 50000, False, '', 0.3),
            ('ENGINE_PM', 'PCV/CCV Filter Check', 'MILEAGE', 50000, False, '', 0.3),
            ('ENGINE_PM', 'Coolant Change & System Flush', 'CALENDAR', 730, False, '', 1.0),
            ('ENGINE_PM', 'Engine Oil Sampling / Analysis', 'MILEAGE', 20000, False, '', 0.3),
            ('ENGINE_PM', 'Radiator Cap & Hose Check', 'MILEAGE', 10000, False, '', 0.3),
            # ── TRANSMISSION ──
            ('TRANSMISSION', 'Transmission Fluid Check', 'MILEAGE', 10000, False, '', 0.3),
            ('TRANSMISSION', 'Transmission Fluid Change', 'MILEAGE', 50000, False, '', 1.0),
            ('TRANSMISSION', 'Clutch Inspection', 'MILEAGE', 20000, False, '', 0.5),
            ('TRANSMISSION', 'Transmission Mount Check', 'MILEAGE', 50000, False, '', 0.3),
            ('TRANSMISSION', 'Gearbox Oil Leak Check', 'MILEAGE', 10000, False, '', 0.2),
            ('TRANSMISSION', 'Clutch Cable & Linkage Inspection', 'MILEAGE', 10000, False, '', 0.3),
            ('TRANSMISSION', 'Clutch Fluid Level Check', 'MILEAGE', 5000, False, '', 0.2),
            ('TRANSMISSION', 'Differential / Axle Oil Check', 'MILEAGE', 10000, False, '', 0.3),
            ('TRANSMISSION', 'Differential Oil Change', 'MILEAGE', 50000, False, '', 1.0),
            ('TRANSMISSION', 'Drive Shaft U-Joint Lubrication', 'MILEAGE', 5000, False, '', 0.3),
            ('TRANSMISSION', 'Drive Shaft Center Bearing Check', 'MILEAGE', 20000, False, '', 0.3),
            ('TRANSMISSION', 'Wheel Bearing Service', 'MILEAGE', 50000, False, '', 1.0),
            # ── BRAKES ──
            ('BRAKES', 'Brake Inspection', 'MILEAGE', 5000, False, '', 0.5),
            ('BRAKES', 'Brake Pad Replacement', 'VISUAL', None, False, '', 2.0),
            ('BRAKES', 'Brake Fluid Flush', 'CALENDAR', 365, False, '', 1.0),
            ('BRAKES', 'Air Dryer Cartridge Replacement', 'MILEAGE', 30000, False, '', 0.5),
            ('BRAKES', 'Brake Chamber Inspection', 'CALENDAR', 180, False, '', 0.5),
            ('BRAKES', 'Slack Adjuster Lubrication', 'MILEAGE', 5000, False, '', 0.3),
            ('BRAKES', 'Spring Brake Inspection', 'CALENDAR', 365, False, '', 0.5),
            ('BRAKES', 'Parking Brake Test', 'MILEAGE', 10000, False, '', 0.3),
            ('BRAKES', 'Brake Rubber Boot & Cap Inspection', 'MILEAGE', 5000, False, '', 0.2),
            ('BRAKES', 'Brake Fluid Level & Top-Up', 'MILEAGE', 5000, False, '', 0.2),
            ('BRAKES', 'Brake Line & Hose Inspection', 'MILEAGE', 10000, False, '', 0.3),
            ('BRAKES', 'Water Brake System Inspection', 'CALENDAR', 90, False, '', 0.5),
            ('BRAKES', 'Water Brake Nozzle Cleaning', 'CALENDAR', 90, False, '', 0.5),
            ('BRAKES', 'Water Brake Pump & Valve Check', 'CALENDAR', 180, False, '', 0.5),
            ('BRAKES', 'Water Brake Tank & Line Check', 'VISUAL', None, False, '', 0.3),
            # ── TIRES ──
            ('TIRES', 'Tire Inspection & Pressure', 'MILEAGE', 1000, False, '', 0.3),
            ('TIRES', 'Tire Rotation', 'MILEAGE', 10000, False, '', 0.5),
            ('TIRES', 'Tire Replacement', 'VISUAL', None, False, '', 1.0),
            ('TIRES', 'Spare Tire Check', 'MILEAGE', 5000, False, '', 0.2),
            ('TIRES', 'Wheel Nut Torque Check', 'MILEAGE', 5000, False, '', 0.3),
            ('TIRES', 'Tire Tread Depth Check', 'MILEAGE', 10000, False, '', 0.2),
            # ── BATTERY & ELECTRICAL ──
            ('BATTERY_ELECTRICAL', 'Battery Load Test', 'MILEAGE', 10000, False, '', 0.3),
            ('BATTERY_ELECTRICAL', 'Battery Replacement', 'VISUAL', None, False, '', 0.5),
            ('BATTERY_ELECTRICAL', 'Battery Cable & Terminal Cleaning', 'MILEAGE', 10000, False, '', 0.3),
            ('BATTERY_ELECTRICAL', 'Alternator Output Test', 'MILEAGE', 20000, False, '', 0.3),
            ('BATTERY_ELECTRICAL', 'Starter Motor Check', 'MILEAGE', 50000, False, '', 0.3),
            ('BATTERY_ELECTRICAL', 'Dashboard Functions & Switch Check', 'MILEAGE', 10000, False, '', 0.3),
            ('BATTERY_ELECTRICAL', 'Lighting Switch & Relay Check', 'MILEAGE', 10000, False, '', 0.2),
            # ── CHASSIS ──
            ('CHASSIS', 'Chassis Lubrication', 'MILEAGE', 5000, False, '', 0.5),
            ('CHASSIS', 'Leaf Spring Inspection', 'MILEAGE', 10000, False, '', 0.3),
            ('CHASSIS', 'U-Bolt Torque Check', 'MILEAGE', 10000, False, '', 0.3),
            ('CHASSIS', 'Kingpin & Fifth Wheel Lubrication', 'MILEAGE', 5000, False, '', 0.3),
            ('CHASSIS', 'Frame Crack Inspection', 'MILEAGE', 20000, False, '', 0.5),
            ('CHASSIS', 'Power Steering Fluid Check', 'MILEAGE', 10000, False, '', 0.2),
            ('CHASSIS', 'Air System Piping & Fitting Check', 'MILEAGE', 10000, False, '', 0.3),
            # ── FUEL SYSTEM ──
            ('FUEL_SYSTEM', 'Water Separator Drain', 'MILEAGE', 5000, False, '', 0.2),
            ('FUEL_SYSTEM', 'Injector Leak-Off Test', 'MILEAGE', 20000, False, '', 0.5),
            ('FUEL_SYSTEM', 'Lift Pump Check', 'MILEAGE', 10000, False, '', 0.3),
            ('FUEL_SYSTEM', 'Primer Bulb Replacement', 'CALENDAR', 365, False, '', 0.3),
            ('FUEL_SYSTEM', 'Fuel Tank Cap & Vent Check', 'MILEAGE', 10000, False, '', 0.2),
            # ── TANK INTEGRITY ──
            ('TANK_INTEGRITY', 'Tank Pressure Test', 'CALENDAR', 365, False, '', 4.0),
            ('TANK_INTEGRITY', 'Ultrasonic Thickness Gauging', 'CALENDAR', 180, False, '', 2.0),
            ('TANK_INTEGRITY', 'Tank Leak Inspection', 'VISUAL', None, False, '', 1.0),
            ('TANK_INTEGRITY', 'Manlid & Hatch Gasket Inspection', 'VISUAL', None, False, '', 0.5),
            ('TANK_INTEGRITY', 'Overfill Prevention System Test', 'CALENDAR', 180, False, '', 1.0),
            ('TANK_INTEGRITY', 'Tank Compartment Inspection', 'CALENDAR', 365, False, '', 1.0),
            # ── VALVES ──
            ('VALVES', 'Internal Valve Service', 'CALENDAR', 180, False, '', 2.0),
            ('VALVES', 'Emergency Valve Test', 'CALENDAR', 90, False, '', 0.5),
            ('VALVES', 'Pressure & Vacuum Vent Inspection', 'CALENDAR', 90, False, '', 0.5),
            ('VALVES', 'API Adapter Seal Check', 'VISUAL', None, False, '', 0.3),
            ('VALVES', 'Butterfly & Ball Valve Service', 'CALENDAR', 180, False, '', 1.0),
            ('VALVES', 'Air-Operated Valve Function Test', 'CALENDAR', 90, False, '', 0.3),
            # ── VAPOR RECOVERY ──
            ('VAPOR_RECOVERY', 'Vapor Return Line Check', 'CALENDAR', 180, False, '', 0.5),
            ('VAPOR_RECOVERY', 'Carbon Canister Service', 'CALENDAR', 365, False, '', 1.0),
            ('VAPOR_RECOVERY', 'Vapor Recovery Coupler Seal Check', 'VISUAL', None, False, '', 0.3),
            ('VAPOR_RECOVERY', 'Vapor Recovery Leak Test', 'CALENDAR', 365, True, 'Vapor Recovery Specialist', 1.0),
            # ── HOSES & COUPLINGS ──
            ('HOSES_COUPLINGS', 'Hose Visual Inspection', 'VISUAL', None, False, '', 0.3),
            ('HOSES_COUPLINGS', 'Hose Pressure Test', 'CALENDAR', 365, False, '', 1.0),
            ('HOSES_COUPLINGS', 'Drop Hose Replacement', 'VISUAL', None, False, '', 0.5),
            ('HOSES_COUPLINGS', 'Hose End Coupling Inspection', 'VISUAL', None, False, '', 0.2),
            ('HOSES_COUPLINGS', 'Camlock Gasket & Arm Inspection', 'VISUAL', None, False, '', 0.3),
            # ── PUMP SYSTEM ──
            ('PUMP_SYSTEM', 'Pump Seal Check', 'CALENDAR', 90, False, '', 0.5),
            ('PUMP_SYSTEM', 'Pump Flow Test', 'CALENDAR', 180, False, '', 1.0),
            ('PUMP_SYSTEM', 'Pump Bearing Lubrication', 'CALENDAR', 180, False, '', 0.3),
            ('PUMP_SYSTEM', 'Pump Strainer Cleaning', 'CALENDAR', 90, False, '', 0.5),
            ('PUMP_SYSTEM', 'PTO Service', 'CALENDAR', 180, False, '', 0.5),
            ('PUMP_SYSTEM', 'Product Delivery Piping Inspection', 'CALENDAR', 180, False, '', 0.5),
            ('PUMP_SYSTEM', 'Piping Flange & Gasket Check', 'VISUAL', None, False, '', 0.3),
            # ── METERING ──
            ('METERING', 'Meter Calibration', 'CALENDAR', 365, True, 'Calibration Specialist', 2.0),
            ('METERING', 'Meter Strainer Cleaning', 'CALENDAR', 90, False, '', 0.5),
            ('METERING', 'Meter Register & Display Check', 'CALENDAR', 180, False, '', 0.3),
            # ── GROUNDING ──
            ('GROUNDING', 'Grounding Cable Continuity Test', 'CALENDAR', 30, False, '', 0.3),
            ('GROUNDING', 'Grounding Reel Inspection', 'CALENDAR', 90, False, '', 0.3),
            ('GROUNDING', 'Grounding Clamp Condition Check', 'VISUAL', None, False, '', 0.2),
            # ── SAFETY EQUIPMENT ──
            ('SAFETY', 'Fire Extinguisher Check', 'CALENDAR', 30, False, '', 0.2),
            ('SAFETY', 'Emergency Shutdown Test', 'CALENDAR', 30, False, '', 0.3),
            ('SAFETY', 'Placard Inspection', 'VISUAL', None, False, '', 0.1),
            ('SAFETY', 'Spill Kit Inspection', 'CALENDAR', 30, False, '', 0.2),
            ('SAFETY', 'PPE Inspection', 'CALENDAR', 90, False, '', 0.2),
            ('SAFETY', 'Wheel Chock & Triangle Check', 'VISUAL', None, False, '', 0.1),
            ('SAFETY', 'MSDS & Label Check', 'CALENDAR', 180, False, '', 0.2),
            ('SAFETY', 'First Aid Kit Inspection', 'CALENDAR', 90, False, '', 0.2),
            ('SAFETY', 'Horn & Warning Device Test', 'MILEAGE', 5000, False, '', 0.2),
            ('SAFETY', 'HAZMAT Placard & Diamond Label Check', 'VISUAL', None, False, '', 0.2),
            ('SAFETY', 'Reflective Tape & Conspicuity Check', 'VISUAL', None, False, '', 0.2),
            ('SAFETY', 'Compartment Product Label Check', 'VISUAL', None, False, '', 0.2),
            ('SAFETY', 'DOST Compliance Sticker Check', 'CALENDAR', 180, False, '', 0.2),
            # ── LIGHTING ──
            ('LIGHTING', 'Brake & Tail Light Check', 'MILEAGE', 5000, False, '', 0.2),
            ('LIGHTING', 'Turn Signal & Hazard Light Check', 'MILEAGE', 5000, False, '', 0.2),
            ('LIGHTING', 'Headlight & High Beam Check', 'MILEAGE', 5000, False, '', 0.2),
            ('LIGHTING', 'License & Clearance Light Check', 'MILEAGE', 5000, False, '', 0.2),
            ('LIGHTING', 'Beacon & Rotating Light Check', 'MILEAGE', 5000, False, '', 0.2),
            # ── WIRING & SENSORS ──
            ('WIRING', 'Wiring Harness Visual Inspection', 'VISUAL', None, False, '', 0.3),
            ('WIRING', 'Sensor Calibration Check', 'CALENDAR', 365, True, 'Electrical Specialist', 1.0),
            ('WIRING', 'ECU & Module Connection Check', 'CALENDAR', 365, False, '', 0.3),
            ('WIRING', 'Instrument Cluster Test', 'MILEAGE', 20000, False, '', 0.3),
            ('WIRING', 'Back-Up Alarm & Camera Check', 'MILEAGE', 10000, False, '', 0.3),
            # ── SUSPENSION ──
            ('SUSPENSION', 'Suspension Inspection', 'MILEAGE', 10000, False, '', 0.5),
            ('SUSPENSION', 'Shock Absorber Check', 'VISUAL', None, False, '', 0.3),
            ('SUSPENSION', 'Air Suspension Bag Inspection', 'MILEAGE', 10000, False, '', 0.3),
            ('SUSPENSION', 'Stabilizer Bar Link Check', 'MILEAGE', 20000, False, '', 0.3),
            # ── EXHAUST ──
            ('EXHAUST', 'Exhaust System Inspection', 'MILEAGE', 20000, False, '', 0.5),
            ('EXHAUST', 'DPF Regeneration Check', 'MILEAGE', 50000, False, '', 0.5),
            ('EXHAUST', 'Exhaust Mount & Bracket Check', 'MILEAGE', 20000, False, '', 0.3),
            # ── HVAC ──
            ('HVAC', 'AC System Check', 'CALENDAR', 180, True, 'HVAC Specialist', 1.0),
            ('HVAC', 'Cabin Air Filter Replacement', 'CALENDAR', 365, False, '', 0.3),
            ('HVAC', 'Defroster System Check', 'CALENDAR', 180, False, '', 0.3),
            # ── HYDRAULICS ──
            ('HYDRAULICS', 'Hydraulic Fluid Check', 'MILEAGE', 5000, False, '', 0.3),
            ('HYDRAULICS', 'Hydraulic Cylinder Inspection', 'CALENDAR', 180, False, '', 0.5),
            ('HYDRAULICS', 'Hydraulic Pump Service', 'CALENDAR', 365, False, '', 1.0),
            ('HYDRAULICS', 'Hydraulic Valve Check', 'CALENDAR', 180, False, '', 0.5),
            # ── BODY & CHASSIS ──
            ('BODY', 'Body & Paint Inspection', 'VISUAL', None, False, '', 0.3),
            ('BODY', 'Mudguard & Splash Guard Check', 'VISUAL', None, False, '', 0.2),
            ('BODY', 'Door & Hinge Lubrication', 'MILEAGE', 5000, False, '', 0.2),
            ('BODY', 'Windshield, Wiper & Washer Check', 'MILEAGE', 5000, False, '', 0.2),
            ('BODY', 'Seat Belt & Mirror Check', 'VISUAL', None, False, '', 0.2),
            ('BODY', 'Cab Mount & Bushing Inspection', 'MILEAGE', 50000, False, '', 0.3),
            ('BODY', 'Tank Steps, Ladder & Platform Check', 'VISUAL', None, False, '', 0.3),
            ('BODY', 'Fall Arrest Anchor Point Inspection', 'CALENDAR', 180, False, '', 0.3),
            ('BODY', 'Static Discharge Chain & Tag Check', 'VISUAL', None, False, '', 0.2),
            # ── INSPECTION & COMPLIANCE ──
            ('INSPECTION', 'Pre-Trip Inspection', 'VISUAL', None, False, '', 0.3),
            ('INSPECTION', 'Post-Trip Inspection', 'VISUAL', None, False, '', 0.3),
            ('INSPECTION', 'LTO Annual Inspection Prep', 'CALENDAR', 365, False, '', 2.0),
            ('INSPECTION', 'Insurance & Registration Check', 'CALENDAR', 365, False, '', 0.2),
            ('INSPECTION', 'Depot Access Compliance Check', 'CALENDAR', 180, False, '', 0.3),
            ('INSPECTION', 'GPS & Telematics Check', 'CALENDAR', 365, False, '', 0.3),
            ('INSPECTION', 'Driver License & Accreditation Check', 'CALENDAR', 180, False, '', 0.2),
        ]
        for cat_code, name, interval_type, interval_value, requires_spec, spec_trade, hours in templates:
            cat = cat_objs[cat_code]
            TaskTemplate.objects.get_or_create(
                category=cat,
                name=name,
                defaults={
                    'interval_type': interval_type,
                    'interval_value': interval_value,
                    'requires_specialist': requires_spec,
                    'specialist_trade': spec_trade,
                    'estimated_labor_hours': hours,
                }
            )
        self.stdout.write(f'  Created {len(templates)} task templates')

        # Create sample trucks
        trucks_data = [
            ('FT-101', 'ABC-1234', 'Isuzu', 'FVR 6x2', 2020, 24000, 'Diesel', 20000, 0),
            ('FT-102', 'XYZ-5678', 'Hino', 'SS 6x4', 2021, 26000, 'Diesel', 15000, 0),
            ('FT-103', 'DEF-9012', 'Mitsubishi', 'Fuso FIGHTER', 2019, 22000, 'Diesel', 35000, 500),
            ('FT-104', 'GHI-3456', 'Isuzu', 'FVM 6x2', 2022, 24000, 'Diesel', 8000, 0),
            ('FT-105', 'JKL-7890', 'Volvo', 'FM 6x4', 2023, 28000, 'Diesel', 5000, 0),
        ]
        for unit, plate, make, model, year, tank_cap, fuel, mileage, hours in trucks_data:
            truck, created = Truck.objects.get_or_create(
                unit_number=unit,
                defaults={
                    'plate_number': plate,
                    'make': make,
                    'model': model,
                    'year': year,
                    'tank_capacity_liters': tank_cap,
                    'fuel_type': fuel,
                    'current_mileage_km': mileage,
                    'current_engine_hours': hours,
                }
            )
            if created:
                self.stdout.write(f'  Created truck: {unit}')

        # Create PM schedules for sample trucks (all templates)
        all_templates = list(TaskTemplate.objects.all())
        for truck in Truck.objects.all()[:3]:
            for tmpl in all_templates:
                PMSchedule.objects.get_or_create(
                    truck=truck,
                    task_template=tmpl,
                    defaults={'is_active': True}
                )
        self.stdout.write('  Created PM schedules for sample trucks')

        # Create sample contractor
        Contractor.objects.get_or_create(
            company_name='WeldingPro Services',
            defaults={
                'contact_person': 'Ricardo Dizon',
                'mobile': '0917-555-1234',
                'email': 'ricardo@weldingpro.ph',
                'skills': 'Welding, Tank Repair, Structural, Pipe Fitting',
                'is_active': True,
            }
        )
        Contractor.objects.get_or_create(
            company_name='Metro Calibration Inc.',
            defaults={
                'contact_person': 'Carla Santos',
                'mobile': '0928-555-5678',
                'email': 'carla@metro-cal.ph',
                'skills': 'Meter Calibration, Precision Measurement, Flow Testing',
                'is_active': True,
            }
        )
        self.stdout.write('  Created sample contractors')

        self.stdout.write(self.style.SUCCESS('Seed data complete!'))
