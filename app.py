
# app.py
import csv
import io
from threading import Thread
import time
from flask import Flask, abort, Blueprint, make_response, render_template, request, redirect, send_from_directory, url_for, flash, session, jsonify, send_file
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import openai
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, date, timezone
from sqlalchemy import create_engine, func, literal
from sqlalchemy import case
from sqlalchemy.ext.hybrid import hybrid_property
from config import Config 
import random
import string
from flask import jsonify, request, current_app
from sqlalchemy import or_
from flask_migrate import Migrate
import json
from werkzeug.utils import secure_filename
import os 
from flask import send_file
import tempfile
from botocore.exceptions import ClientError
from cryptography.fernet import Fernet
import boto3 
import uuid
from datetime import datetime, timezone
import zipfile
import hashlib
from sqlalchemy import text
from apscheduler.schedulers.background import BackgroundScheduler
from openai import OpenAI, APITimeoutError, APIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from itsdangerous import URLSafeTimedSerializer
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length

# Initialize Flask app
app = Flask(__name__)
app.config.from_object('config.Config')
Config.init_fernet(app)
db = SQLAlchemy(app, session_options={"autoflush": False, "autocommit": False})
migrate = Migrate(app, db)

auth_bp = Blueprint('auth', __name__)
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
PROFILE_PICTURE_FOLDER = os.path.join(UPLOAD_FOLDER, 'profile_pictures')
os.makedirs(PROFILE_PICTURE_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'U3VwZXJTZWNyZXRBZG1pblRva2VuMTIzIQ')  # Provide default only for development
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///clinic.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', UPLOAD_FOLDER)
app.config['BACKUP_FOLDER'] = os.getenv('BACKUP_FOLDER', 'backups')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB max upload size
app.config.from_object(Config)
app.config['FERNET_KEY'] = os.getenv('FERNET_KEY')
app.config['DEEPSEEK_API_KEY'] = os.getenv('DEEPSEEK_API_KEY')
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', 'your.email@gmail.com')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', 'your-password-or-app-password')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'your.email@gmail.com')


mail = Mail(app)
ts = URLSafeTimedSerializer(app.config['SECRET_KEY'])

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'

if not os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pictures')):
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pictures'))


class ResetPasswordRequestForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', 
                                   validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')

# Database Models
class User(db.Model, UserMixin):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    profile_picture = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password, password)
    
    def get_id(self):
        return str(self.id)
        # Relationship to Sales (as pharmacist)
    def update_last_login(self):
        self.last_login = datetime.now(timezone.utc)  # Changed from utcnow()
        db.session.commit()


class BackupRecord(db.Model):
    __tablename__ = 'backup_records'
    
    id = db.Column(db.Integer, primary_key=True)
    backup_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    backup_type = db.Column(db.String(20), nullable=False)  # 'manual', 'scheduled', 'disaster_recovery'
    status = db.Column(db.String(20), nullable=False, default='pending')  # 'pending', 'in_progress', 'completed', 'failed'
    size_bytes = db.Column(db.Integer)
    storage_location = db.Column(db.String(255))  # S3 path or local path
    checksum = db.Column(db.String(64))  # SHA-256 checksum
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    notes = db.Column(db.Text)
    
    user = db.relationship('User', backref='backups')
    
    def __repr__(self):
        return f'<BackupRecord {self.backup_id}>'

class DisasterRecoveryPlan(db.Model):
    __tablename__ = 'disaster_recovery_plans'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    recovery_point_objective = db.Column(db.Integer)  # in minutes
    recovery_time_objective = db.Column(db.Integer)  # in minutes
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_tested = db.Column(db.DateTime)
    test_results = db.Column(db.Text)
    
    def __repr__(self):
        return f'<DisasterRecoveryPlan {self.name}>'

class Ward(db.Model):
    __tablename__ = 'wards'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    
    beds = db.relationship('Bed', backref='ward', lazy=True)

class Bed(db.Model):
    __tablename__ = 'beds'
    
    id = db.Column(db.Integer, primary_key=True)
    bed_number = db.Column(db.String(50), nullable=False, unique=True)
    ward_id = db.Column(db.Integer, db.ForeignKey('wards.id'), nullable=False)
    status = db.Column(db.String(20), default='available')  # available, occupied, maintenance
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    
    patient = db.relationship('Patient', backref='bed_assignment')

def get_total_beds():
    return Bed.query.count()

def get_available_beds():
    return Bed.query.filter_by(status='available').count()

def get_occupied_beds():
    return Bed.query.filter_by(status='occupied').count()

class Drug(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    drug_number = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    specification = db.Column(db.String(200))
    buying_price = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    stocked_quantity = db.Column(db.Integer, nullable=False)
    sold_quantity = db.Column(db.Integer, default=0)
    expiry_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    @hybrid_property
    def remaining_quantity(self):
        return self.stocked_quantity - self.sold_quantity
    
    @remaining_quantity.expression
    def remaining_quantity(cls):
        return cls.stocked_quantity - cls.sold_quantity
    
    def update_stock(self, quantity):
        """Safe method to update stock quantities"""
        if self.remaining_quantity >= quantity:
            self.sold_quantity += quantity
            db.session.add(self)
            return True
        return False
    
    @hybrid_property
    def stock_status(self):
        if self.remaining_quantity == 0:
            return 'out-of-stock'
        elif self.remaining_quantity < 10:
            return 'low-stock'
        elif (self.expiry_date - date.today()).days < 30:
            return 'expiring-soon'
        return 'in-stock'
    
    @stock_status.expression
    def stock_status(cls):
        return case([
            (cls.remaining_quantity == 0, 'out-of-stock'),
            (cls.remaining_quantity < 10, 'low-stock'),
            (cls.expiry_date <= date.today() + timedelta(days=30), 'expiring-soon')
        ], else_='in-stock')
    
    def update_stock(self, quantity):
        """Safe method to update stock quantities"""
        if self.remaining_quantity >= quantity:
            self.sold_quantity += quantity  # Update the underlying column
            return True
        return False  
    
class DrugDosage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    drug_id = db.Column(db.Integer, db.ForeignKey('drug.id'), nullable=False)
    indication = db.Column(db.Text)
    contraindication = db.Column(db.Text)
    interaction = db.Column(db.Text)
    side_effects = db.Column(db.Text)
    dosage_peds = db.Column(db.Text)
    dosage_adults = db.Column(db.Text)
    dosage_geriatrics = db.Column(db.Text)
    important_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    
    drug = db.relationship('Drug', backref='dosage')


class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    op_number = db.Column(db.String(20), unique=True)
    ip_number = db.Column(db.String(20), unique=True)
    name = db.Column(db.String(100), nullable=False)  # encrypted
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    address = db.Column(db.String(200))  # encrypted
    phone = db.Column(db.String(20))  # encrypted
    destination = db.Column(db.String(100))
    occupation = db.Column(db.String(100))  # encrypted
    religion = db.Column(db.String(100))
    nok_name = db.Column(db.String(100))  # encrypted
    nok_contact = db.Column(db.String(20))  # encrypted
    tca = db.Column(db.Date)
    date_of_admission = db.Column(db.Date)
    status = db.Column(db.String(20), default='active')
    chief_complaint = db.Column(db.Text)
    history_present_illness = db.Column(db.Text)
    
    # AI Integration Fields
    ai_assistance_enabled = db.Column(db.Boolean, default=False)
    ai_diagnosis = db.Column(db.Text)
    ai_treatment_recommendations = db.Column(db.Text)
    ai_last_updated = db.Column(db.DateTime)
    ai_confidence_score = db.Column(db.Float)  # 0-1 scale for diagnosis confidence

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    reviews = db.relationship('PatientReviewSystem', backref='patient', lazy=True)
    histories = db.relationship('PatientHistory', backref='patient', lazy=True)
    examinations = db.relationship('PatientExamination', backref='patient', lazy=True)
    diagnoses = db.relationship('PatientDiagnosis', backref='patient', lazy=True)
    management = db.relationship('PatientManagement', backref='patient', lazy=True)
    lab_requests = db.relationship('LabRequest', backref='patient', lazy=True)
    imaging_requests = db.relationship('ImagingRequest', backref='patient', lazy=True)
    @property
    def decrypted_name(self):
        if not self.name:
            return None
        try:
            return Config.decrypt_data_static(self.name)
        except Exception:
            return "[Decryption Error]"

    @property 
    def decrypted_address(self):
        return Config.decrypt_data_static(self.address)

    @property
    def decrypted_phone(self):
        return Config.decrypt_data_static(self.phone)

    @property
    def decrypted_occupation(self):
        return Config.decrypt_data_static(self.occupation)

    @property
    def decrypted_nok_name(self):
        return Config.decrypt_data_static(self.nok_name)

    @property
    def decrypted_nok_contact(self):
        return Config.decrypt_data_static(self.nok_contact)
    def get_ai_recommendations(self):
        """Return formatted AI recommendations if available"""
        if not self.ai_assistance_enabled or not self.ai_diagnosis:
            return None
        
        return {
            'diagnosis': self.ai_diagnosis,
            'treatment': self.ai_treatment_recommendations,
            'last_updated': self.ai_last_updated.strftime('%Y-%m-%d %H:%M') if self.ai_last_updated else None,
            'confidence': f"{round(self.ai_confidence_score * 100, 1)}%" if self.ai_confidence_score else None
        }
    
    def get_ai_summary(self):
        """Generate a concise summary of AI findings"""
        if not self.ai_assistance_enabled:
            return "AI assistance not enabled for this patient"
        
        summary = []
        if self.ai_diagnosis:
            summary.append(f"AI Diagnosis: {self.ai_diagnosis.splitlines()[0]}")
        if self.ai_treatment_recommendations:
            summary.append(f"Treatment Suggestions: {self.ai_treatment_recommendations.splitlines()[0]}")
        if self.ai_confidence_score:
            summary.append(f"Confidence: {round(self.ai_confidence_score * 100, 1)}%")
        
        return "\n".join(summary) if summary else "No AI recommendations available"

    
class PatientReviewSystem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    cns = db.Column(db.Text)
    cvs = db.Column(db.Text)
    rs = db.Column(db.Text)
    git = db.Column(db.Text)
    gut = db.Column(db.Text)
    skin = db.Column(db.Text)
    msk = db.Column(db.Text)
    
    # AI fields
    ai_suggested_questions = db.Column(db.Text)  # Stores AI-generated questions for review of systems
    ai_last_updated = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class PatientHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    social_history = db.Column(db.Text)
    medical_history = db.Column(db.Text)
    surgical_history = db.Column(db.Text)
    family_history = db.Column(db.Text)
    allergies = db.Column(db.Text)
    medications = db.Column(db.Text)
    
    # AI fields
    ai_identified_risk_factors = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class PatientExamination(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    general_appearance = db.Column(db.Text)
    jaundice = db.Column(db.Boolean, default=False)
    pallor = db.Column(db.Boolean, default=False)
    cyanosis = db.Column(db.Boolean, default=False)
    lymphadenopathy = db.Column(db.Boolean, default=False)
    edema = db.Column(db.Boolean, default=False)
    dehydration = db.Column(db.Boolean, default=False)
    dehydration_parameters = db.Column(db.Text)
    temperature = db.Column(db.Float)
    pulse = db.Column(db.Integer)
    resp_rate = db.Column(db.Integer)
    bp_systolic = db.Column(db.Integer)
    bp_diastolic = db.Column(db.Integer)
    spo2 = db.Column(db.Integer)
    weight = db.Column(db.Float)
    height = db.Column(db.Float)
    bmi = db.Column(db.Float)
    cvs_exam = db.Column(db.Text)
    resp_exam = db.Column(db.Text)
    abdo_exam = db.Column(db.Text)
    cns_exam = db.Column(db.Text)
    msk_exam = db.Column(db.Text)
    skin_exam = db.Column(db.Text)
    
    # AI fields
    ai_identified_red_flags = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class PatientDiagnosis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    working_diagnosis = db.Column(db.Text)
    differential_diagnosis = db.Column(db.Text)
    
        # AI fields
    ai_supported_diagnosis = db.Column(db.Boolean, default=False)
    ai_alternative_diagnoses = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class PatientManagement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    treatment_plan = db.Column(db.Text)
    follow_up = db.Column(db.Text)
    notes = db.Column(db.Text)   
     
    # AI fields
    ai_generated_plan = db.Column(db.Boolean, default=False)
    ai_alternative_treatments = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class LabRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('lab_test.id'), nullable=False)
    requested_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, completed, cancelled
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ImagingRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('imaging_test.id'), nullable=False)
    requested_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, completed, cancelled
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ImagingTest(db.Model):
    """Model for imaging tests available in the clinic"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<ImagingTest {self.name}>'

class LabRequestItem(db.Model):
    """Model for individual items in a lab request"""
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('lab_request.id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('lab_test.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, completed, cancelled
    results = db.Column(db.Text)
    comments = db.Column(db.Text)
    performed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    performed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    test = db.relationship('LabTest', backref='request_items')
    performer = db.relationship('User', backref='performed_lab_tests')

    def __repr__(self):
        return f'<LabRequestItem {self.id} for test {self.test_id}>'

class LabTest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class PatientLab(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('lab_test.id'), nullable=False)
    results = db.Column(db.Text)
    comments = db.Column(db.Text)
    performed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    reviewed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
        
    patient = db.relationship('Patient', backref='labs')
    test = db.relationship('LabTest', backref='patient_labs')
    performer = db.relationship('User', foreign_keys=[performed_by])
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])

# Enhanced AIService class with more comprehensive AI integration
class AIService:
    
    MODELS = {
        'primary': 'deepseek-chat',  # Update based on verification
        'fallback': 'gpt-3.5-turbo'  # Optional fallback
    }

    @classmethod
    def get_client(cls):
        """Get AI client with proper configuration"""
        api_key = current_app.config.get('DEEPSEEK_API_KEY')
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is not configured")
        
        return OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
            timeout=30.0
        )
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=(retry_if_exception_type(APITimeoutError) | 
              retry_if_exception_type(APIError)),
        reraise=True
    )
    
    @staticmethod
    def generate_review_systems_questions(patient_data):
        """Generate focused review of systems questions based on chief complaint and biodata"""
        prompt = f"""
        As an experienced physician, suggest the most relevant review of systems questions for this patient:
        
        Patient: {patient_data.get('age')}
        Patient: {patient_data.get('address', 'Not specified')}
        Patient: {patient_data['age']} year old {patient_data['gender']}
        Chief Complaint: {patient_data['chief_complaint']}
        Occupation: {patient_data.get('occupation', 'Not specified')}
        
        Provide:
        1. 3-5 most relevant systems to review based on the chief complaint
        2. 2-3 specific questions for each relevant system
        3. Format as a bulleted list with clear system headings
        
        Focus on questions that would help identify important positives/negatives basing on the most likeley differentials diagnosis according to patient data in age, gender, occupation, address and chief complain.
        """
        
        try:
            response = deepseek_client.chat.completions.create(
                model="deepseek-chat",  # Changed from "deepseek-medical"
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            current_app.logger.error(f"AI Review Systems Error: {str(e)}")
            return None

    @staticmethod
    def generate_hpi_questions(patient_data):
        """Generate HPI questions using SOCRATES framework with retries and fallbacks"""
        prompt = AIService._build_hpi_prompt(patient_data)
        
        for model_name in AIService.MODELS.values():
            try:
                response = AIService.get_client().chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=800
                )
                return response.choices[0].message.content
            except Exception as e:
                logging.warning(f"Model {model_name} failed: {str(e)}")
                continue
                
        return None

    @staticmethod
    def log_ai_error(method_name, error, patient_data=None):
        """Centralized error logging"""
        error_info = {
            "error": str(error),
            "type": type(error).__name__,
            "patient_data": patient_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        current_app.logger.error(
            f"AI {method_name} Error",
            extra={"error_details": error_info},
            exc_info=True
        )
        
    @staticmethod
    def generate_hpi_content(patient_data):
        """Robust HPI generation with model verification"""
        prompt = AIService._build_hpi_prompt(patient_data)
        
        for model_name in AIService.MODELS.values():
            try:
                response = AIService.get_client().chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=800,
                    timeout=60  # Reduced timeout for individual requests
                )
                return response.choices[0].message.content
            except Exception as e:
                logging.warning(f"Model {model_name} failed: {str(e)}")
                continue
                
        return None

    @staticmethod
    def _build_hpi_prompt(patient_data):
        """Construct a detailed HPI prompt with proper validation and structure
        
        Args:
            patient_data (dict): Dictionary containing patient information including:
                - age
                - gender
                - address 
                - occupation
                - chief_complaint
                - review_of_systems
        
        Returns:
            str: A well-structured prompt for AI-generated HPI content
        """
     
        age = patient_data.get('age', 'unknown age')
        gender = patient_data.get('gender', 'unknown gender')
        address = patient_data.get('address', 'address not specified')
        occupation = patient_data.get('occupation', 'occupation not specified')
        chief_complaint = patient_data.get('chief_complaint', 'unspecified complaint')
        review_systems = patient_data.get('review_systems', 'not documented')
        
        return f"""
        As an experienced physician, generate a comprehensive History of Present Illness (HPI) 
        for this patient case following the SOCRATES framework and including all relevant details:

        Patient Background:
        - age: {age} 
        - gender {gender}
        - address: {address}
        - Occupation: {occupation}
        - Chief Complaint: "{chief_complaint}"
        - Review of Systems: {review_systems}

        Required HPI Structure:
        1. Opening Statement:
        - Start with a concise opening that introduces the patient and chief complaint

        2. Symptom Analysis (SOCRATES):
        a) Site: Location of symptoms with radiation patterns
        b) Onset: When it began and circumstances of onset
        c) Character: Quality and nature of symptoms
        d) Radiation: Where symptoms spread/migrate
        e) Associated Symptoms: Other related symptoms
        f) Time Course: Progression since onset
        g) Exacerbating/Relieving Factors: What makes it better/worse
        h) Severity: Quantitative measure (e.g., pain scale)

        3. Contextual Factors:
        - Impact on daily activities and work
        - Any previous treatments attempted and their effects
        - Relevant psychosocial factors
        - Occupational exposures or risk factors

        4. Summary:
        - Brief synthesis of key findings
        - Any red flags or urgent concerns

        Additional Instructions:
        - Use professional medical terminology but keep it clear
        - Organize information logically
        - Include pertinent positives and negatives
        - For pain complaints, use the OPQRST mnemonic if applicable
        - Highlight any findings that suggest urgent evaluation

        Please generate the HPI in full paragraph narrative format suitable for a medical record.
        """

    @staticmethod
    def generate_diagnosis(patient_data):
        """
        Generate comprehensive diagnosis with differentials and supporting evidence
        """
        prompt = f"""
        Analyze this patient case and provide diagnostic recommendations:
        
        Patient: {patient_data['age']} year old {patient_data['gender']}
        Chief Complaint: {patient_data['chief_complaint']}
        HPI: {patient_data.get('hpi', 'Not yet documented')}
        Review of Systems: {patient_data.get('review_systems', 'Not yet documented')}
        Medical History: {patient_data.get('medical_history', 'Not significant')}
        Examination Findings: {patient_data.get('examination', 'Not yet documented')}
        
        Provide:
        1. Primary working diagnosis with supporting evidence
        2. 3-5 differential diagnoses in order of likelihood
        3. Key findings that support each diagnosis
        4. Important negatives that rule out alternatives
        5. Recommended diagnostic tests to confirm
        """
        
    @staticmethod
    def generate_diagnosis(patient_data):
        """Generate diagnosis with proper error handling"""
        prompt = f"""
        [Your diagnosis prompt here...]
        """
        
        try:
            # Initialize client outside try block to make it available in fallback
            client = None
            client = AIService.get_client()
            
            # Try primary model
            response = client.chat.completions.create(
                model=AIService.MODELS['primary'],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000,
                timeout=20
            )
            return response.choices[0].message.content
        
        except Exception as primary_error:
            current_app.logger.error(f"Primary model failed: {str(primary_error)}")
            
            try:
                # Ensure client is available for fallback
                if client is None:
                    client = AIService.get_client()
                
                # Try fallback model
                response = client.chat.completions.create(
                    model=AIService.MODELS['fallback'],
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=1000,
                    timeout=20
                )
                current_app.logger.warning("Used fallback model successfully")
                return response.choices[0].message.content
                
            except Exception as fallback_error:
                current_app.logger.error(f"Fallback model failed: {str(fallback_error)}")
                return None
            
    @staticmethod
    def analyze_lab_results(patient_data, lab_text):
        """
        Analyze lab results in context of patient presentation
        """
        prompt = f"""
        Analyze these lab results in the context of the patient's presentation:
        
        Patient: {patient_data['age']} year old {patient_data['gender']}
        Chief Complaint: {patient_data['chief_complaint']}
        Working Diagnosis: {patient_data.get('diagnosis', 'Not yet established')}
        
        Lab Results:
        {lab_text}
        
        Provide:
        1. Interpretation of abnormal values
        2. How results support or contradict working diagnosis
        3. Any new diagnostic considerations
        4. Recommendations for follow-up testing if needed
        """
        
        try:
            response = deepseek_client.chat.completions.create(
                model="deepseek-medical",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=800
            )
            return response.choices[0].message.content
        except Exception as e:
            current_app.logger.error(f"AI Lab Analysis Error: {str(e)}")
            return None

    @staticmethod
    def generate_treatment_plan(patient_data, available_drugs):
        """
        Generate comprehensive treatment plan considering available drugs
        """
        drugs_list = "\n".join([f"- {drug.name} ({drug.specification})" for drug in available_drugs])
        
        prompt = f"""
        Create a treatment plan for this patient considering available medications:
        
        Patient: {patient_data['age']} year old {patient_data['gender']}
        Diagnosis: {patient_data['diagnosis']}
        Allergies: {patient_data.get('allergies', 'None known')}
        Current Medications: {patient_data.get('medications', 'None')}
        
        Available Drugs:
        {drugs_list}
        
        Provide:
        1. First-line treatment recommendations using available drugs
        2. Alternative options if first-line isn't available
        3. Specific dosages based on patient factors
        4. Duration of treatment
        5. Monitoring recommendations
        6. Patient education points
        7. Follow-up plan
        """
        
        try:
            response = deepseek_client.chat.completions.create(
                model="deepseek-medical",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1200
            )
            return response.choices[0].message.content
        except Exception as e:
            current_app.logger.error(f"AI Treatment Plan Error: {str(e)}")
            return None

class DebtPayment(db.Model):
    __tablename__ = 'debt_payments'
    
    id = db.Column(db.Integer, primary_key=True)
    debt_id = db.Column(db.Integer, db.ForeignKey('debts.id'))
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Added this line
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = db.relationship('User', backref='debt_payments')

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, dispensed, cancelled
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
  
    items = db.relationship('PrescriptionItem', backref='prescription', lazy=True)  
    patient = db.relationship('Patient', backref='prescriptions')
    doctor = db.relationship('User', backref='prescriptions')

class PrescriptionItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescription.id'), nullable=False)
    drug_id = db.Column(db.Integer, db.ForeignKey('drug.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    dosage = db.Column(db.Text)
    frequency = db.Column(db.String(50))
    duration = db.Column(db.String(50))
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, dispensed, cancelled
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    drug = db.relationship('Drug', backref='prescription_items')

class Sale(db.Model):
    __tablename__ = 'sales'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_number = db.Column(db.String(50), unique=True, nullable=False)
    bulk_sale_number = db.Column(db.String(20))
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pharmacist_name = db.Column(db.String(100))  # Store pharmacist name directly
    total_amount = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0)
    payment_method = db.Column(db.String(20))
    status = db.Column(db.String(20), default='completed')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    patient = db.relationship('Patient', backref='patient_sales')
    user = db.relationship('User', foreign_keys=[user_id], backref='user_sales')
    items = db.relationship('SaleItem', back_populates='sale', lazy=True, cascade='all, delete-orphan')


class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    drug_id = db.Column(db.Integer, db.ForeignKey('drug.id'))
    drug_name = db.Column(db.String(100))  # Store drug name directly
    drug_specification = db.Column(db.String(200))  # Store drug specs
    individual_sale_number = db.Column(db.String(20))
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'))
    lab_test_id = db.Column(db.Integer, db.ForeignKey('lab_test.id'))
    description = db.Column(db.String(200), nullable=False, default="Drug sale")
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    drug = db.relationship('Drug', backref='sale_items')
    service = db.relationship('Service', backref='sale_items')
    lab_test = db.relationship('LabTest', backref='sale_items')
    sale = db.relationship('Sale', back_populates='items')

    def __init__(self, **kwargs):
        super(SaleItem, self).__init__(**kwargs)
        # Automatically set drug info when drug is assigned
        if self.drug:
            self.drug_name = self.drug.name
            self.drug_specification = self.drug.specification

class Refund(db.Model):
    __tablename__ = 'refunds'
    
    id = db.Column(db.Integer, primary_key=True)
    refund_number = db.Column(db.String(50), unique=True, nullable=False)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), default='completed')
    
    # Relationships
    sale = db.relationship('Sale', backref='refunds')
    user = db.relationship('User', backref='refunds')
    items = db.relationship('RefundItem', back_populates='refund')

class RefundItem(db.Model):
    __tablename__ = 'refund_items'  # Note the correct table name
    
    id = db.Column(db.Integer, primary_key=True)
    refund_id = db.Column(db.Integer, db.ForeignKey('refunds.id'), nullable=False)
    sale_item_id = db.Column(db.Integer, db.ForeignKey('sale_items.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    
    # Relationships
    refund = db.relationship('Refund', back_populates='items')
    sale_item = db.relationship('SaleItem', backref='refund_items')

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_number = db.Column(db.String(50), unique=True, nullable=False)
    transaction_type = db.Column(db.String(50), nullable=False)  # sale, refund, payment, expense, etc.
    amount = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reference_id = db.Column(db.Integer)  # ID of related record (sale, expense, etc.)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user = db.relationship('User', backref='transactions')

def generate_transaction_number():
    return f"TXN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{random.randint(100, 999)}"

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    purpose = db.Column(db.String(200))
    status = db.Column(db.String(20), default='scheduled')  # scheduled, confirmed, cancelled, completed
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    patient = db.relationship('Patient', backref='appointments')
    doctor = db.relationship('User', backref='appointments')

class Debt(db.Model):
    __tablename__ = 'debts'
    
    id = db.Column(db.Integer, primary_key=True)
    debt_number = db.Column(db.String(50), unique=True, nullable=False)
    debt_type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    creditor = db.Column(db.String(100), nullable=False)
    due_date = db.Column(db.Date)
    interest_rate = db.Column(db.Float, default=0.0)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='active')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    payments = db.relationship('DebtPayment', backref='debt', lazy=True)


def generate_debt_number():
    return f"DEBT-{datetime.now().strftime('%Y%m%d')}-{generate_random_string(4)}"

class Expense(db.Model):
    __tablename__ = 'expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    expense_number = db.Column(db.String(50), unique=True, nullable=False)
    expense_type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    description = db.Column(db.Text)
    due_date = db.Column(db.Date)
    payment_method = db.Column(db.String(20))
    status = db.Column(db.String(20), default='paid')  # paid, pending, cancelled
    paid_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='expenses')

def generate_expense_number():
    return f"EXP-{datetime.now().strftime('%Y%m%d')}-{generate_random_string(4)}"

class Purchase(db.Model):
    __tablename__ = 'purchases'
    
    id = db.Column(db.Integer, primary_key=True)
    purchase_number = db.Column(db.String(50), unique=True, nullable=False)
    purchase_type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    purchase_date = db.Column(db.Date, nullable=False)
    supplier = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

def generate_purchase_number():
    return f"PUR-{datetime.now().strftime('%Y%m%d')}-{generate_random_string(4)}"

class Employee(db.Model):
    __tablename__ = 'employees'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.String(100))
    salary = db.Column(db.Float)
    hire_date = db.Column(db.Date)
    contact = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    payrolls = db.relationship('Payroll', backref='employee', lazy=True)
    user = db.relationship('User', backref='employee')


class Payroll(db.Model):
    __tablename__ = 'payrolls'
    
    id = db.Column(db.Integer, primary_key=True)
    payroll_number = db.Column(db.String(50), unique=True, nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'))
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    pay_period = db.Column(db.String(50))
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


def generate_payroll_number():
    return f"PAY-{datetime.now().strftime('%Y%m%d')}-{generate_random_string(4)}"

class Customer(db.Model):
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(100))
    email = db.Column(db.String(100))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    payments = db.relationship('DebtorPayment', backref='customer', lazy=True)

class DebtorPayment(db.Model):
    __tablename__ = 'debtor_payments'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    reference = db.Column(db.String(100))
    notes = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class PatientService(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    notes = db.Column(db.Text)
    performed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    patient = db.relationship('Patient', backref='services')
    service = db.relationship('Service', backref='patient_services')
    performer = db.relationship('User', foreign_keys=[performed_by])

class Debtor(db.Model):
    __tablename__ = 'debtors'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(100))
    email = db.Column(db.String(100))
    Total_debt = db.Column(db.Float, nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    amount_owed = db.Column(db.Float, default=0.0)
    last_payment_date = db.Column(db.Date)
    next_payment_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    table_name = db.Column(db.String(50))  # Tracks which table was affected
    record_id = db.Column(db.Integer)      # ID of the affected record
    description = db.Column(db.String(255))  # For backward compatibility
    changes = db.Column(db.JSON)           # Structured change data
    old_values = db.Column(db.JSON)        # Previous values before change
    new_values = db.Column(db.JSON)        # Values after change
    ip_address = db.Column(db.String(50))  # IP address of the requester
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


    # Relationship
    user = db.relationship('User', backref='audit_log_entries')

    def __init__(self, **kwargs):
        if 'description' not in kwargs and 'changes' in kwargs:
            kwargs['description'] = str(kwargs.get('changes'))
        super().__init__(**kwargs)

    def to_dict(self):
        """Returns audit log entry as dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'table_name': self.table_name,
            'record_id': self.record_id,
            'description': self.description,
            'changes': self.changes,
            'old_values': self.old_values,
            'new_values': self.new_values,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'user': {
                'id': self.user.id,
                'username': self.user.username
            } if self.user else None
        }

def generate_random_string(length=6):
    """Helper function to generate random strings"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))



# Replace with this:
_first_request = True

@app.before_request
def initialize_data():
    global _first_request
    if not _first_request:
        return
    _first_request = False
    
    # Create all database tables
    db.create_all()

    # Create default admin if not exists
    if not db.session.query(User).filter_by(role='admin').first():
        admin = User(
            username='Makokha Nelson',
            email='makokhanelson4@gmail.com',
            role='admin',
            is_active=True
        )
        admin.set_password('Doc.makokha@2024')
        db.session.add(admin)
    
    # Create default doctor if not exists
    if not db.session.query(User).filter_by(role='doctor').first():
        doctor = User(
            username='Default Doctor',
            email='doctor@clinic.com',
            role='doctor',
            is_active=True
        )
        doctor.set_password('Doctor@123')
        db.session.add(doctor)
    
    # Create default pharmacist if not exists
    if not db.session.query(User).filter_by(role='pharmacist').first():
        pharmacist = User(
            username='Default Pharmacist',
            email='pharmacist@clinic.com',
            role='pharmacist',
            is_active=True
        )
        pharmacist.set_password('Pharmacist@123')
        db.session.add(pharmacist)
    
    # Create default receptionist if not exists
    if not db.session.query(User).filter_by(role='receptionist').first():
        receptionist = User(
            username='Default Receptionist',
            email='receptionist@clinic.com',
            role='receptionist',
            is_active=True
        )
        receptionist.set_password('Receptionist@123')
        db.session.add(receptionist)
    
    # Commit all changes at once
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error initializing data: {str(e)}")


# Login Manager
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Audit logging function
def log_audit(action, table=None, record_id=None, user_id=None, changes=None, 
             old_values=None, new_values=None, ip_address=None):
    """
    Logs an audit trail entry with comprehensive tracking
    
    Args:
        action (str): The action performed (e.g., 'create', 'update', 'delete')
        table (str): Name of the database table affected
        record_id: ID of the affected record
        user_id: ID of the user performing the action
        changes (dict): Summary of changes made (for complex operations)
        old_values: Previous values before change (for updates)
        new_values: New values after change (for updates)
        ip_address: IP address of the requester
    """
    try:
        user_id = user_id if user_id is not None else (
            current_user.id if current_user.is_authenticated else None
        )
        
        ip_address = ip_address if ip_address is not None else request.remote_addr
        
        changes_data = None
        if changes:
            changes_data = json.dumps(changes, default=str)
        elif new_values is not None:
            changes_data = json.dumps({'new_values': new_values}, default=str)
        
        log = AuditLog(
            user_id=user_id,
            action=action,
            table_name=table,
            record_id=record_id,
            changes=changes_data,
            old_values=str(old_values) if old_values else None,
            new_values=str(new_values) if new_values else None,
            ip_address=ip_address,
            created_at=datetime.now(timezone.utc)  # Changed from timestamp
        )
        
        db.session.add(log)
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to log audit trail: {str(e)}")

# Utility functions
def generate_patient_number(patient_type):
    prefix = 'OP' if patient_type == 'OP' else 'IP'
    last_patient = Patient.query.filter(
        Patient.op_number.isnot(None) if patient_type == 'OP' else Patient.ip_number.isnot(None)
    ).order_by(Patient.id.desc()).first()
    
    if last_patient:
        last_number = last_patient.op_number if patient_type == 'OP' else last_patient.ip_number
        last_seq = int(last_number.split('MNC')[-1])
        new_seq = last_seq + 1
    else:
        new_seq = 1
    
    return f"{prefix}MNC{new_seq:03d}"

def generate_sale_number():
    now = datetime.now()
    return f"SALE-{now.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

def generate_bulk_sale_number():
    now = datetime.now()
    return f"BULK-{now.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

def generate_individual_sale_number():
    now = datetime.now()
    return f"ITEM-{now.strftime('%Y%m%d')}-{random.randint(100, 999)}"

# In your home route:
@app.route('/')
def home():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'doctor':
            return redirect(url_for('doctor_dashboard'))
        elif current_user.role == 'pharmacist':
            return redirect(url_for('pharmacist_dashboard'))
        elif current_user.role == 'receptionist':
            return redirect(url_for('receptionist_dashboard'))
    return redirect(url_for('auth.login'))
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != '' and allowed_file(file.filename):
                os.makedirs(PROFILE_PICTURE_FOLDER, exist_ok=True)
                filename = secure_filename(file.filename)
                timestamp = str(int(time.time()))
                filename = f"user_{current_user.id}_{timestamp}_{filename}"
                filepath = os.path.join(PROFILE_PICTURE_FOLDER, filename)
                file.save(filepath)
                if current_user.profile_picture:
                    old_path = os.path.join(app.root_path, 'static', current_user.profile_picture)
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except Exception as e:
                            app.logger.error(f"Error deleting old profile picture: {str(e)}")

                current_user.profile_picture = os.path.join('uploads', 'profile_pictures', filename).replace('\\', '/')

        current_user.username = request.form.get('username', current_user.username)
        current_user.email = request.form.get('email', current_user.email)
        
        new_password = request.form.get('new_password')
        if new_password:
            if check_password_hash(current_user.password, request.form.get('current_password')):
                current_user.set_password(new_password)
                flash('Password updated successfully!', 'success')
            else:
                flash('Current password is incorrect', 'danger')
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('profile.html', user=current_user)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter((User.email == email) | (User.username == email)).first()
        
        if user and user.check_password(password) and user.is_active and user.role == role:
            login_user(user, remember=remember)
            user.last_login = datetime.utcnow()
            db.session.commit()
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        
        flash('Invalid credentials or role', 'danger')
    
    return render_template('index.html')

@app.context_processor
def inject_current_date():
    return {'current_date': date.today().strftime('%Y-%m-%d')}
@app.route('/logout')
@login_required
def logout():
    log_audit('logout')
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))  # Changed from 'login' to 'auth.login'


def send_async_email(app, msg):
    """Send email asynchronously in a background thread."""
    with app.app_context():
        mail.send(msg)

def send_password_reset_email(user_email, token):
    reset_url = url_for('auth.reset_token', token=token, _external=True)
    
    msg = Message(
        "Reset Your Password",
        recipients=[user_email],
        html=f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2d3748;">Password Reset Request</h2>
            <p>Click the button below to reset your password:</p>
            <a href="{reset_url}" 
               style="display: inline-block; padding: 10px 20px; 
                      background-color: #4299e1; color: white; 
                      text-decoration: none; border-radius: 4px;">
                Reset Password
            </a>
            <p style="margin-top: 20px; color: #718096;">
                This link expires in 1 hour. If you didn't request this, please ignore this email.
            </p>
        </div>
        """
    )
    Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()

# Generate token
def generate_reset_token(email):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt=current_app.config['SECURITY_PASSWORD_SALT'])

# Verify token
def verify_reset_token(token, max_age=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(
            token,
            salt=current_app.config['SECURITY_PASSWORD_SALT'],
            max_age=max_age
        )
        return email
    except:
        return False
@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_request():
    form = ResetPasswordRequestForm()  # Create form instance
    
    if form.validate_on_submit():  # Use validate_on_submit for proper form validation
        email = form.email.data
        user = User.query.filter_by(email=email).first()
        if user:
            token = generate_reset_token(user.email)
            send_password_reset_email(user.email, token)
            flash('Password reset link sent to your email', 'info')
            return redirect(url_for('auth.login'))
        flash('Email not found', 'danger')
    
    # Pass the form to the template
    return render_template('auth/reset_request.html', form=form)

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    email = verify_reset_token(token)
    if not email:
        flash('Invalid or expired token', 'danger')
        return redirect(url_for('auth.reset_request'))
    
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('auth.reset_request'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        user.set_password(password)  # Your password hashing method
        db.session.commit()
        flash('Password updated successfully!', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_token.html', token=token)
@auth_bp.route('/reset-password', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def reset_password():
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        email = form.email.data
        user = User.query.filter_by(email=email).first()
        
        if user:
            serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
            token = serializer.dumps(email, salt=current_app.config['SECURITY_PASSWORD_SALT'])
            reset_url = url_for('auth.reset_with_token', token=token, _external=True)
            
            if send_password_reset_email(email, reset_url):
                flash('A password reset link has been sent to your email.', 'info')
            else:
                flash('Failed to send email. Please try again later.', 'danger')
            return redirect(url_for('auth.login'))
        
        flash('If this email exists in our system, a reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset.html', form=form)

@auth_bp.route('/reset/<token>', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def reset_with_token(token):
    try:
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        email = serializer.loads(
            token,
            salt=current_app.config['SECURITY_PASSWORD_SALT'],
            max_age=current_app.config['RESET_TOKEN_EXPIRATION']
        )
    except:
        flash('The reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.reset_password'))
    
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Invalid user.', 'danger')
        return redirect(url_for('auth.reset_password'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been updated successfully!', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_with_token.html', form=form, token=token)

@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    try:
        total_drugs = db.session.query(func.count(Drug.id)).scalar()
        low_stock = db.session.query(func.count(Drug.id)).filter(
            Drug.stocked_quantity - Drug.sold_quantity < 10
        ).scalar()
        
        expiring_soon = db.session.query(func.count(Drug.id)).filter(
            Drug.expiry_date <= date.today() + timedelta(days=30)
        ).scalar()
        
        today_sales = db.session.query(func.sum(Sale.total_amount)).filter(
            func.date(Sale.created_at) == date.today()
        ).scalar() or 0
        
        monthly_sales = db.session.query(func.sum(Sale.total_amount)).filter(
            func.strftime('%Y-%m', Sale.created_at) == datetime.now().strftime('%Y-%m')
        ).scalar() or 0
        
        pending_bills = db.session.query(func.sum(Debtor.amount_owed)).scalar() or 0
        
        last_backup = BackupRecord.query.filter_by(status='completed')\
            .order_by(BackupRecord.timestamp.desc()).first()
        last_backup_time = last_backup.timestamp if last_backup else 'Never'
        
        backup_stats = {
            'total_backups': BackupRecord.query.count(),
            'successful_backups': BackupRecord.query.filter_by(status='completed').count(),
            'failed_backups': BackupRecord.query.filter_by(status='failed').count(),
            'total_size_mb': db.session.query(
                func.coalesce(func.sum(BackupRecord.size_bytes), 0) / (1024 * 1024)
            ).scalar()
        }
        
        active_users = db.session.query(func.count(User.id)).filter_by(is_active=True).scalar()
        
        # Get doctor statistics - ensure these are called
        daily_stats = get_doctor_stats('daily')
        monthly_stats = get_doctor_stats('monthly')
        yearly_stats = get_doctor_stats('yearly')
        
        # Get recent activity
        recent_activity = db.session.query(
            AuditLog.id,
            AuditLog.action,
            AuditLog.created_at.label('created_at'),
            literal('audit').label('type')
        ).union_all(
            db.session.query(
                BackupRecord.id,
                literal('backup').label('action'),
                BackupRecord.timestamp.label('created_at'),
                literal('backup').label('type')
            )
        ).order_by(text('created_at')).limit(10).all()
        
        return render_template('admin/dashboard.html',
            total_drugs=total_drugs,
            low_stock=low_stock,
            expiring_soon=expiring_soon,
            today_sales=today_sales,
            monthly_sales=monthly_sales,
            pending_bills=pending_bills,
            last_backup_time=last_backup_time,
            backup_stats=backup_stats,
            active_users=active_users,
            daily_stats=daily_stats,
            monthly_stats=monthly_stats,
            yearly_stats=yearly_stats,
            recent_activity=recent_activity
        )
    
    except Exception as e:
        app.logger.error(f"Error in admin dashboard: {str(e)}")
        flash('An error occurred while loading the dashboard', 'danger')
        return redirect(url_for('home'))

def get_total_beds():
    return Bed.query.count()

def get_available_beds():
    return Bed.query.filter_by(status='available').count()

def get_occupied_beds():
    return Bed.query.filter_by(status='occupied').count()

def get_doctor_stats(timeframe='daily'):
    """Get statistics for doctors based on timeframe (daily, monthly, yearly)"""
    today = date.today()
    
    if timeframe == 'daily':
        start_date = today
        end_date = today + timedelta(days=1)
    elif timeframe == 'monthly':
        start_date = date(today.year, today.month, 1)
        end_date = date(today.year, today.month + 1, 1) if today.month < 12 else date(today.year + 1, 1, 1)
    elif timeframe == 'yearly':
        start_date = date(today.year, 1, 1)
        end_date = date(today.year + 1, 1, 1)
    else:
        start_date = today
        end_date = today + timedelta(days=1)

    # Get inpatient and outpatient counts
    inpatients = db.session.query(Patient).filter(
        Patient.ip_number.isnot(None),
        Patient.date_of_admission >= start_date,
        Patient.date_of_admission < end_date
    ).count()

    outpatients = db.session.query(Patient).filter(
        Patient.op_number.isnot(None),
        Patient.date_of_admission >= start_date,
        Patient.date_of_admission < end_date
    ).count()

    # Get discharged patients
    discharged = db.session.query(Patient).filter(
        Patient.status == 'completed',
        Patient.updated_at >= start_date,
        Patient.updated_at < end_date
    ).count()

    # Get bed statistics with zero division protection
    total_beds = get_total_beds()
    occupied_beds = get_occupied_beds()
    available_beds = get_available_beds()
    
    # Calculate occupancy rate with zero division protection
    occupancy_rate = 0
    if total_beds > 0:
        occupancy_rate = (occupied_beds / total_beds) * 100

    return {
        'inpatients': inpatients,
        'outpatients': outpatients,
        'discharged': discharged,
        'occupied_beds': occupied_beds,
        'available_beds': available_beds,
        'total_beds': total_beds,
        'occupancy_rate': occupancy_rate,
        'timeframe': timeframe,
        'start_date': start_date,
        'end_date': end_date - timedelta(days=1)  # Subtract 1 day to show inclusive end data
    }

# Backup utility functions
def create_backup(backup_id):
    """Create a database backup in background"""
    backup = BackupRecord.query.get(backup_id)
    if not backup:
        return
    
    try:
        # Create a temporary file
        temp_dir = tempfile.mkdtemp()
        backup_file = os.path.join(temp_dir, f'backup_{backup.backup_id}.zip')
        
        # Create a ZIP file containing all table data as JSON
        with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Backup each table
            for table_name in BACKUP_CONFIG['tables_to_backup']:
                try:
                    # Get table data
                    result = db.engine.execute(f'SELECT * FROM {table_name}')
                    rows = [dict(row) for row in result]
                    
                    # Convert to JSON
                    table_data = json.dumps(rows, indent=2, default=str)
                    
                    # Add to ZIP
                    zipf.writestr(f'{table_name}.json', table_data)
                except Exception as e:
                    app.logger.error(f'Error backing up table {table_name}: {str(e)}')
                    continue
            
            # Add metadata
            metadata = {
                'backup_id': backup.backup_id,
                'timestamp': datetime.utcnow().isoformat(),
                'database_url': str(db.engine.url),
                'tables_backed_up': BACKUP_CONFIG['tables_to_backup'],
                'app_version': '1.0.0'
            }
            zipf.writestr('metadata.json', json.dumps(metadata, indent=2))
        
        # Calculate checksum
        with open(backup_file, 'rb') as f:
            file_hash = hashlib.sha256()
            while chunk := f.read(8192):
                file_hash.update(chunk)
            checksum = file_hash.hexdigest()
        
        # Encrypt the backup
        cipher_suite = Fernet(BACKUP_CONFIG['encryption_key'].encode())
        with open(backup_file, 'rb') as f:
            encrypted_data = cipher_suite.encrypt(f.read())
        
        encrypted_file = backup_file + '.enc'
        with open(encrypted_file, 'wb') as f:
            f.write(encrypted_data)
        
        # Get file size
        file_size = os.path.getsize(encrypted_file)
        
        # Store backup (local or S3)
        if s3_client:
            # Upload to S3
            s3_key = f'backups/{backup.backup_id}.zip.enc'
            s3_client.upload_file(
                encrypted_file,
                BACKUP_CONFIG['s3_bucket'],
                s3_key,
                ExtraArgs={
                    'Metadata': {
                        'backup-id': backup.backup_id,
                        'checksum': checksum,
                        'created-by': str(current_user.id)
                    }
                }
            )
            storage_location = f's3://{BACKUP_CONFIG["s3_bucket"]}/{s3_key}'
        else:
            # Store locally
            local_backup_dir = BACKUP_CONFIG['local_storage_path']
            os.makedirs(local_backup_dir, exist_ok=True)
            local_path = os.path.join(local_backup_dir, f'{backup.backup_id}.zip.enc')
            os.rename(encrypted_file, local_path)
            storage_location = local_path
        
        # Update backup record
        backup.status = 'completed'
        backup.size_bytes = file_size
        backup.storage_location = storage_location
        backup.checksum = checksum
        db.session.commit()
        
        # Clean up
        try:
            os.remove(backup_file)
            if os.path.exists(encrypted_file):
                os.remove(encrypted_file)
            os.rmdir(temp_dir)
        except:
            pass
        
    except Exception as e:
        app.logger.error(f'Backup failed: {str(e)}', exc_info=True)
        backup.status = 'failed'
        backup.notes = f'Error: {str(e)}'
        db.session.commit()

@app.route('/admin/beds', methods=['GET', 'POST'])
@login_required
def manage_beds():
    # Simple admin check
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    # Rest of your function code remains the same
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_ward':
            try:
                ward = Ward(
                    name=request.form.get('ward_name'),
                    description=request.form.get('ward_description')
                )
                db.session.add(ward)
                db.session.commit()
                flash('Ward added successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding ward: {str(e)}', 'danger')
        
        elif action == 'add_bed':
            try:
                bed = Bed(
                    bed_number=request.form.get('bed_number'),
                    ward_id=request.form.get('ward_id'),
                    status='available'
                )
                db.session.add(bed)
                db.session.commit()
                flash('Bed added successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding bed: {str(e)}', 'danger')
        
        elif action == 'assign_bed':
            try:
                bed_id = request.form.get('bed_id')
                patient_id = request.form.get('patient_id')
                
                bed = Bed.query.get(bed_id)
                if bed.status == 'occupied':
                    flash('Bed is already occupied', 'danger')
                else:
                    bed.status = 'occupied'
                    bed.patient_id = patient_id
                    db.session.commit()
                    flash('Bed assigned successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error assigning bed: {str(e)}', 'danger')
        
        elif action == 'release_bed':
            try:
                bed_id = request.form.get('bed_id')
                bed = Bed.query.get(bed_id)
                bed.status = 'available'
                bed.patient_id = None
                db.session.commit()
                flash('Bed released successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error releasing bed: {str(e)}', 'danger')
        
        return redirect(url_for('manage_beds'))
    
    wards = Ward.query.all()
    beds = Bed.query.order_by(Bed.ward_id, Bed.bed_number).all()
    patients = Patient.query.filter_by(status='active').all()
    
    return render_template('admin/beds.html',
        wards=wards,
        beds=beds,
        patients=patients,
        total_beds=get_total_beds(),
        occupied_beds=get_occupied_beds(),
        available_beds=get_available_beds()
    )

@app.route('/admin/drugs', methods=['GET', 'POST'])
@login_required
def manage_drugs():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            try:
                drug = Drug(
                    drug_number=generate_drug_number(),
                    name=request.form.get('name'),
                    specification=request.form.get('specification'),
                    buying_price=float(request.form.get('buying_price')),
                    selling_price=float(request.form.get('selling_price')),
                    stocked_quantity=int(request.form.get('stocked_quantity')),
                    expiry_date=datetime.strptime(request.form.get('expiry_date'), '%Y-%m-%d').date()
                )
                db.session.add(drug)
                db.session.commit()
                
                log_audit('create', 'Drug', drug.id, None, {
                    'drug_number': drug.drug_number,
                    'name': drug.name,
                    'specification': drug.specification,
                    'buying_price': drug.buying_price,
                    'selling_price': drug.selling_price,
                    'stocked_quantity': drug.stocked_quantity,
                    'expiry_date': drug.expiry_date
                })
                
                flash('Drug added successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding drug: {str(e)}', 'danger')
        
        elif action == 'edit':
            drug_id = request.form.get('drug_id')
            drug = db.session.get(Drug, drug_id)  # Updated to use session.get()
            if drug:
                try:
                    old_values = {
                        'drug_number': drug.drug_number,
                        'name': drug.name,
                        'specification': drug.specification,
                        'buying_price': drug.buying_price,
                        'selling_price': drug.selling_price,
                        'stocked_quantity': drug.stocked_quantity,
                        'expiry_date': drug.expiry_date
                    }
                    
                    drug.name = request.form.get('name')
                    drug.specification = request.form.get('specification')
                    drug.buying_price = float(request.form.get('buying_price'))
                    drug.selling_price = float(request.form.get('selling_price'))
                    drug.stocked_quantity = int(request.form.get('stocked_quantity'))
                    drug.expiry_date = datetime.strptime(request.form.get('expiry_date'), '%Y-%m-%d').date()
                    
                    db.session.commit()
                    
                    log_audit('update', 'Drug', drug.id, old_values, {
                        'drug_number': drug.drug_number,
                        'name': drug.name,
                        'specification': drug.specification,
                        'buying_price': drug.buying_price,
                        'selling_price': drug.selling_price,
                        'stocked_quantity': drug.stocked_quantity,
                        'expiry_date': drug.expiry_date
                    })
                    
                    flash('Drug updated successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error updating drug: {str(e)}', 'danger')
            else:
                flash('Drug not found', 'danger')
        
        elif action == 'delete':
            drug_id = request.form.get('drug_id')
            drug = db.session.get(Drug, drug_id)  # Updated to use session.get()
            if drug:
                try:
                    log_audit('delete', 'Drug', drug.id, {
                        'drug_number': drug.drug_number,
                        'name': drug.name,
                        'specification': drug.specification,
                        'buying_price': drug.buying_price,
                        'selling_price': drug.selling_price,
                        'stocked_quantity': drug.stocked_quantity,
                        'expiry_date': drug.expiry_date
                    }, None)
                    
                    db.session.delete(drug)
                    db.session.commit()
                    flash('Drug deleted successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error deleting drug: {str(e)}', 'danger')
            else:
                flash('Drug not found', 'danger')
        
        return redirect(url_for('manage_drugs'))
    
    # Handle filter requests
    filter_type = request.args.get('filter', 'all')
    
    # Base query
    query = db.select(Drug)
    
    if filter_type == 'low_stock':
        # Drugs with less than 10 remaining
        query = query.where(Drug.remaining_quantity < 10)
    elif filter_type == 'expiring_soon':
        # Drugs expiring in the next 30 days or already expired
        today = datetime.now().date()
        thirty_days_later = today + timedelta(days=30)
        query = query.where(Drug.expiry_date <= thirty_days_later).order_by(Drug.expiry_date)
    elif filter_type == 'out_of_stock':
        # Drugs with zero or negative remaining quantity
        query = query.where(Drug.remaining_quantity <= 0)
    elif filter_type == 'expired':
        # Only expired drugs
        today = datetime.now().date()
        query = query.where(Drug.expiry_date < today)
    
    # Execute the query
    drugs = db.session.execute(query).scalars().all()
    
    total_value = sum(drug.selling_price * drug.remaining_quantity for drug in drugs)
    return render_template('admin/drugs.html', 
                         drugs=drugs, 
                         total_value=total_value, 
                         current_filter=filter_type,
                         today=datetime.now().date())

@app.route('/admin/drugs/<int:drug_id>')
@login_required
def get_drug(drug_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    drug = db.session.get(Drug, drug_id)  # Updated to use session.get()
    if not drug:
        return jsonify({'error': 'Drug not found'}), 404
    
    return jsonify({
        'id': drug.id,
        'drug_number': drug.drug_number,
        'name': drug.name,
        'specification': drug.specification,
        'buying_price': drug.buying_price,
        'selling_price': drug.selling_price,
        'stocked_quantity': drug.stocked_quantity,
        'sold_quantity': drug.sold_quantity,
        'expiry_date': drug.expiry_date.strftime('%Y-%m-%d'),
        'remaining_quantity': drug.remaining_quantity,
        'is_expired': drug.expiry_date < datetime.now().date(),
        'expires_soon': drug.expiry_date <= (datetime.now().date() + timedelta(days=30))
    })

@app.route('/admin/users', methods=['GET', 'POST'])
@login_required
def manage_users():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            try:
                if User.query.filter_by(username=request.form.get('username')).first():
                    flash('Username already exists', 'danger')
                    return redirect(url_for('manage_users'))
                
                if User.query.filter_by(email=request.form.get('email')).first():
                    flash('Email already exists', 'danger')
                    return redirect(url_for('manage_users'))
                
                user = User(
                    username=request.form.get('username'),
                    email=request.form.get('email'),
                    role=request.form.get('role'),
                    phone=request.form.get('phone'),
                    is_active=True if request.form.get('is_active') else False,
                    last_login=None  # Initialize last_login as None for new users
                )
                user.set_password(request.form.get('password'))
                db.session.add(user)
                db.session.commit()
                
                log_audit('create', 'User', user.id, None, {
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                    'phone': user.phone,
                    'is_active': user.is_active,
                    'last_login': user.last_login
                })
                
                flash('User added successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding user: {str(e)}', 'danger')
        
        elif action == 'edit':
            user_id = request.form.get('user_id')
            user = User.query.get(user_id)
            if user:
                try:
                    old_values = {
                        'username': user.username,
                        'email': user.email,
                        'role': user.role,
                        'phone': user.phone,
                        'is_active': user.is_active,
                        'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else None
                    }
                    
                    user.username = request.form.get('username')
                    user.email = request.form.get('email')
                    user.role = request.form.get('role')
                    user.phone = request.form.get('phone')
                    user.is_active = True if request.form.get('is_active') else False
                    
                    if request.form.get('password'):
                        user.set_password(request.form.get('password'))
                    
                    db.session.commit()
                    
                    log_audit('update', 'User', user.id, old_values, {
                        'username': user.username,
                        'email': user.email,
                        'role': user.role,
                        'phone': user.phone,
                        'is_active': user.is_active,
                        'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else None
                    })
                    
                    flash('User updated successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error updating user: {str(e)}', 'danger')
            else:
                flash('User not found', 'danger')
        
        elif action == 'delete':
            user_id = request.form.get('user_id')
            user = User.query.get(user_id)
            if user:
                if user.id == current_user.id:
                    flash('You cannot delete your own account', 'danger')
                else:
                    try:
                        log_audit('delete', 'User', user.id, {
                            'username': user.username,
                            'email': user.email,
                            'role': user.role,
                            'phone': user.phone,
                            'is_active': user.is_active,
                            'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else None
                        }, None)
                        
                        db.session.delete(user)
                        db.session.commit()
                        flash('User deleted successfully!', 'success')
                    except Exception as e:
                        db.session.rollback()
                        flash(f'Error deleting user: {str(e)}', 'danger')
            else:
                flash('User not found', 'danger')
        
        return redirect(url_for('manage_users'))
    
    # Order users by last login (most recent first) and then by username
    users = User.query.order_by(User.last_login.desc().nullslast(), User.username.asc()).all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/employees', methods=['GET', 'POST'])
@login_required
def manage_employees():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            try:
                employee = Employee(
                    name=request.form.get('name'),
                    position=request.form.get('position'),
                    salary=float(request.form.get('salary')) if request.form.get('salary') else None,
                    hire_date=datetime.strptime(request.form.get('hire_date'), '%Y-%m-%d').date() if request.form.get('hire_date') else None,
                    contact=request.form.get('contact'),
                    user_id=request.form.get('user_id') if request.form.get('user_id') else None
                )
                db.session.add(employee)
                db.session.commit()
                
                log_audit('create', 'Employee', employee.id, None, {
                    'name': employee.name,
                    'position': employee.position,
                    'salary': employee.salary,
                    'hire_date': str(employee.hire_date) if employee.hire_date else None,
                    'contact': employee.contact,
                    'user_id': employee.user_id
                })
                
                flash('Employee added successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding employee: {str(e)}', 'danger')
        
        elif action == 'edit':
            employee_id = request.form.get('employee_id')
            employee = Employee.query.get(employee_id)
            if employee:
                try:
                    old_values = {
                        'name': employee.name,
                        'position': employee.position,
                        'salary': employee.salary,
                        'hire_date': str(employee.hire_date) if employee.hire_date else None,
                        'contact': employee.contact,
                        'user_id': employee.user_id
                    }
                    
                    employee.name = request.form.get('name')
                    employee.position = request.form.get('position')
                    employee.salary = float(request.form.get('salary')) if request.form.get('salary') else None
                    employee.hire_date = datetime.strptime(request.form.get('hire_date'), '%Y-%m-%d').date() if request.form.get('hire_date') else None
                    employee.contact = request.form.get('contact')
                    employee.user_id = request.form.get('user_id') if request.form.get('user_id') else None
                    
                    db.session.commit()
                    
                    log_audit('update', 'Employee', employee.id, old_values, {
                        'name': employee.name,
                        'position': employee.position,
                        'salary': employee.salary,
                        'hire_date': str(employee.hire_date) if employee.hire_date else None,
                        'contact': employee.contact,
                        'user_id': employee.user_id
                    })
                    
                    flash('Employee updated successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error updating employee: {str(e)}', 'danger')
            else:
                flash('Employee not found', 'danger')
        
        elif action == 'delete':
            employee_id = request.form.get('employee_id')
            employee = Employee.query.get(employee_id)
            if employee:
                try:
                    log_audit('delete', 'Employee', employee.id, {
                        'name': employee.name,
                        'position': employee.position,
                        'salary': employee.salary,
                        'hire_date': str(employee.hire_date) if employee.hire_date else None,
                        'contact': employee.contact,
                        'user_id': employee.user_id
                    }, None)
                    
                    db.session.delete(employee)
                    db.session.commit()
                    flash('Employee deleted successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error deleting employee: {str(e)}', 'danger')
            else:
                flash('Employee not found', 'danger')
        
        return redirect(url_for('manage_employees'))
    
    employees = Employee.query.all()
    users = User.query.filter(User.role != 'admin').all()
    return render_template('admin/employees.html', 
                        employees=employees, 
                        users=users,
                        User=User)  # Pass the User model to template

@app.route('/admin/employees/<int:employee_id>')
@login_required
def get_employee(employee_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    employee = Employee.query.get_or_404(employee_id)
    return jsonify({
        'id': employee.id,
        'name': employee.name,
        'position': employee.position,
        'salary': employee.salary,
        'hire_date': employee.hire_date.strftime('%Y-%m-%d') if employee.hire_date else None,
        'contact': employee.contact,
        'user_id': employee.user_id
    })

@app.route('/admin/reports', methods=['GET', 'POST'])
@login_required
def admin_reports():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    drug_report = None
    service_report = None
    start_date = None
    end_date = None
    
    if request.method == 'POST':
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        report_type = request.form.get('report_type')
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            if start_date > end_date:
                flash('Start date cannot be after end date', 'danger')
                return redirect(url_for('admin_reports'))
            
            if report_type == 'drug_sales':
                # Generate drug sales report
                drug_sales = db.session.query(
                    SaleItem.drug_name,
                    func.sum(SaleItem.quantity).label('total_units'),
                    func.sum(SaleItem.total_price).label('total_amount'),
                    func.sum((SaleItem.unit_price - Drug.buying_price) * SaleItem.quantity).label('total_profit')
                ).join(
                    Drug, SaleItem.drug_id == Drug.id
                ).join(
                    Sale, SaleItem.sale_id == Sale.id
                ).filter(
                    Sale.created_at >= start_date,
                    Sale.created_at <= end_date + timedelta(days=1),
                    SaleItem.drug_id.isnot(None)
                ).group_by(
                    SaleItem.drug_name
                ).order_by(
                    SaleItem.drug_name
                ).all()
                
                # Calculate totals
                total_sales = sum(sale.total_amount for sale in drug_sales)
                total_profit = sum(sale.total_profit for sale in drug_sales)
                
                drug_report = {
                    'sales': drug_sales,
                    'total_sales': total_sales,
                    'total_profit': total_profit,
                    'start_date': start_date,
                    'end_date': end_date
                }
                
            elif report_type == 'patient_services':
                # Generate patient service report
                service_data = db.session.query(
                    PatientService.service_id,
                    Service.name,
                    func.count(PatientService.id).label('total_services'),
                    func.sum(Service.price).label('total_amount')
                ).join(
                    Service, PatientService.service_id == Service.id
                ).filter(
                    PatientService.created_at >= start_date,
                    PatientService.created_at <= end_date + timedelta(days=1)
                ).group_by(
                    PatientService.service_id,
                    Service.name
                ).order_by(
                    Service.name
                ).all()
                
                # Calculate totals
                total_services = sum(service.total_services for service in service_data)
                total_amount = sum(service.total_amount for service in service_data)
                
                service_report = {
                    'services': service_data,
                    'total_services': total_services,
                    'total_amount': total_amount,
                    'start_date': start_date,
                    'end_date': end_date
                }
                
        except ValueError:
            flash('Invalid date format', 'danger')
    
    return render_template('admin/reports.html',
        drug_report=drug_report,
        service_report=service_report,
        start_date=start_date,
        end_date=end_date
    )

@app.route('/admin/reports/generate', methods=['GET'])
@login_required
def generate_reports():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get parameters (default to drug_sales if not specified)
    report_type = request.args.get('type', 'drug_sales')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    # Validate required parameters
    if not start_date_str or not end_date_str:
        return jsonify({'error': 'Both start and end dates are required'}), 400
    
    try:
        # Parse dates
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() + timedelta(days=1)
        
        if start_date > end_date:
            return jsonify({'error': 'Start date must be before end date'}), 400
    
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    
    if report_type == 'drug_sales':
        # Drug sales report logic
        drugs = db.session.query(
            Drug.name,
            func.sum(SaleItem.quantity).label('units_sold'),
            func.sum(SaleItem.total_price).label('total_sales'),
            func.sum((SaleItem.unit_price - Drug.buying_price) * SaleItem.quantity).label('profit')
        ).join(SaleItem).join(Sale).filter(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed'
        ).group_by(Drug.name).all()
        
        return jsonify({
            'status': 'success',
            'report_type': 'drug_sales',
            'start_date': start_date_str,
            'end_date': end_date_str,
            'data': [{
                'name': d.name,
                'units_sold': d.units_sold,
                'total_sales': float(d.total_sales),
                'profit': float(d.profit)
            } for d in drugs]
        })
    
    elif report_type == 'patient_services':
        # Patient services report logic
        services = db.session.query(
            Service.name,
            func.count(SaleItem.id).label('count'),
            func.sum(SaleItem.total_price).label('total_revenue'),
            Patient.first_name,
            Patient.last_name
        ).join(SaleItem, SaleItem.service_id == Service.id)\
         .join(Sale, SaleItem.sale_id == Sale.id)\
         .join(Patient, Sale.patient_id == Patient.id)\
         .filter(
            Sale.created_at >= start_date,
            Sale.created_at <= end_date,
            Sale.status == 'completed'
        ).group_by(Service.name, Patient.first_name, Patient.last_name).all()
        
        return jsonify({
            'status': 'success',
            'report_type': 'patient_services',
            'start_date': start_date_str,
            'end_date': end_date_str,
            'data': [{
                'service_name': s.name,
                'patient_name': f"{s.first_name} {s.last_name}",
                'count': s.count,
                'total_revenue': float(s.total_revenue) if s.total_revenue else 0
            } for s in services]
        })
    
    return jsonify({'error': 'Invalid report type'}), 400

@app.route('/admin/transactions')
@login_required
def manage_transactions():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    transactions = Transaction.query.order_by(Transaction.created_at.desc()).all()
    return render_template('admin/transactions.html', transactions=transactions)


# Configuration for backup
BACKUP_CONFIG = {
    'local_storage_path': os.path.join(app.instance_path, 'backups'),
    's3_bucket': os.getenv('AWS_BACKUP_BUCKET', 'your-backup-bucket'),
    'encryption_key': os.getenv('BACKUP_ENCRYPTION_KEY', Fernet.generate_key().decode()),
    'tables_to_backup': [
        'users', 'transactions', 'expenses', 'purchases', 'payroll', 
        'debtors', 'employees', 'customers', 'drugs', 'drug_dosages'
    ]
}

# Initialize S3 client if configured
if os.getenv('AWS_ACCESS_KEY_ID'):
    s3_client = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION', 'us-east-1')
    )
else:
    s3_client = None

@app.route('/admin/backup', methods=['GET', 'POST'])
@login_required
def backup_management():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create_backup':
            try:
                # Create a new backup record
                backup = BackupRecord(
                    backup_type='manual',
                    user_id=current_user.id,
                    notes=request.form.get('notes', ''),
                    status='in_progress'
                )
                db.session.add(backup)
                db.session.commit()
                
                # Run backup in background
                from threading import Thread
                thread = Thread(target=create_backup, args=(backup.id,))
                thread.start()
                
                flash('Backup process started successfully. You will be notified when complete.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error initiating backup: {str(e)}', 'danger')
        
        elif action == 'restore_backup':
            backup_id = request.form.get('backup_id')
            backup = BackupRecord.query.get_or_404(backup_id)
            
            try:
                # Verify backup exists
                if not verify_backup_exists(backup):
                    flash('Backup file not found', 'danger')
                    return redirect(url_for('backup_management'))
                
                # Run restore in background
                from threading import Thread
                thread = Thread(target=restore_backup, args=(backup.id,))
                thread.start()
                
                flash('Restore process started successfully. The system may be unavailable during restoration.', 'warning')
            except Exception as e:
                flash(f'Error initiating restore: {str(e)}', 'danger')
        
        elif action == 'download_backup':
            backup_id = request.form.get('backup_id')
            backup = BackupRecord.query.get_or_404(backup_id)
            
            try:
                if not verify_backup_exists(backup):
                    flash('Backup file not found', 'danger')
                    return redirect(url_for('backup_management'))
                
                # Get backup file
                backup_file = get_backup_file(backup)
                
                # Create a response with the backup file
                response = send_file(
                    backup_file,
                    as_attachment=True,
                    download_name=f'backup_{backup.backup_id}.zip',
                    mimetype='application/zip'
                )
                
                # Log download activity
                log_audit('download', 'BackupRecord', backup.id, None, {'downloaded_by': current_user.id})
                
                return response
            except Exception as e:
                flash(f'Error downloading backup: {str(e)}', 'danger')
        
        elif action == 'delete_backup':
            backup_id = request.form.get('backup_id')
            backup = BackupRecord.query.get_or_404(backup_id)
            
            try:
                # Delete from storage
                delete_backup_file(backup)
                
                # Delete record
                db.session.delete(backup)
                db.session.commit()
                
                flash('Backup deleted successfully', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error deleting backup: {str(e)}', 'danger')
        
        return redirect(url_for('backup_management'))
    
    # Get all backups ordered by most recent
    backups = BackupRecord.query.order_by(BackupRecord.timestamp.desc()).all()
    
    # Get disaster recovery plans
    recovery_plans = DisasterRecoveryPlan.query.all()
    
    return render_template('admin/backup.html', backups=backups, recovery_plans=recovery_plans)

@app.route('/admin/disaster_recovery', methods=['GET', 'POST'])
@login_required
def disaster_recovery():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create_recovery_plan':
            try:
                plan = DisasterRecoveryPlan(
                    name=request.form.get('name'),
                    description=request.form.get('description'),
                    recovery_point_objective=int(request.form.get('rpo', 1440)),  # Default 24 hours
                    recovery_time_objective=int(request.form.get('rto', 240)),   # Default 4 hours
                    is_active=True
                )
                db.session.add(plan)
                db.session.commit()
                flash('Disaster recovery plan created successfully', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error creating recovery plan: {str(e)}', 'danger')
        
        elif action == 'update_recovery_plan':
            plan_id = request.form.get('plan_id')
            plan = DisasterRecoveryPlan.query.get_or_404(plan_id)
            
            try:
                plan.name = request.form.get('name', plan.name)
                plan.description = request.form.get('description', plan.description)
                plan.recovery_point_objective = int(request.form.get('rpo', plan.recovery_point_objective))
                plan.recovery_time_objective = int(request.form.get('rto', plan.recovery_time_objective))
                plan.is_active = request.form.get('is_active', 'off') == 'on'
                db.session.commit()
                flash('Disaster recovery plan updated successfully', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating recovery plan: {str(e)}', 'danger')
        
        elif action == 'test_recovery_plan':
            plan_id = request.form.get('plan_id')
            plan = DisasterRecoveryPlan.query.get_or_404(plan_id)
            
            try:
                # Find most recent backup
                backup = BackupRecord.query.filter_by(status='completed')\
                    .order_by(BackupRecord.timestamp.desc())\
                    .first()
                
                if not backup:
                    flash('No valid backups found for recovery testing', 'danger')
                    return redirect(url_for('disaster_recovery'))
                
                # Run test restore in background
                from threading import Thread
                thread = Thread(target=test_disaster_recovery, args=(plan.id, backup.id))
                thread.start()
                
                flash('Disaster recovery test initiated. You will be notified when complete.', 'info')
            except Exception as e:
                flash(f'Error initiating recovery test: {str(e)}', 'danger')
        
        return redirect(url_for('disaster_recovery'))
    
    # Get all recovery plans
    recovery_plans = DisasterRecoveryPlan.query.all()
    
    return render_template('admin/disaster_recovery.html', recovery_plans=recovery_plans)

@app.route('/admin/backup/status/<int:backup_id>')
@login_required
def backup_status(backup_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    backup = BackupRecord.query.get_or_404(backup_id)
    return jsonify({
        'id': backup.id,
        'status': backup.status,
        'timestamp': backup.timestamp.isoformat(),
        'size_bytes': backup.size_bytes,
        'notes': backup.notes
    })

@app.route('/admin/backup/logs')
@login_required
def backup_logs():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get last 50 backup operations
    backups = BackupRecord.query.order_by(BackupRecord.timestamp.desc()).limit(50).all()
    
    return jsonify([{
        'id': b.id,
        'backup_id': b.backup_id,
        'timestamp': b.timestamp.isoformat(),
        'type': b.backup_type,
        'status': b.status,
        'size_mb': round(b.size_bytes / (1024 * 1024), 2) if b.size_bytes else None,
        'user': b.user.username if b.user else 'System'
    } for b in backups])

# ======================
# BACKUP IMPLEMENTATION
# ======================

def create_backup(backup_id):
    """Create a database backup in background"""
    backup = db.session.get(BackupRecord, backup_id)  # Updated to use session.get()
    if not backup:
        return
    
    try:
        # Create a temporary file
        temp_dir = tempfile.mkdtemp()
        backup_file = os.path.join(temp_dir, f'backup_{backup.backup_id}.zip')
        
        # Create a ZIP file containing all table data as JSON
        with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Backup each table
            for table_name in BACKUP_CONFIG['tables_to_backup']:
                try:
                    # Get table data using SQLAlchemy 2.0 syntax
                    with db.engine.connect() as conn:
                        result = conn.execute(text(f'SELECT * FROM {table_name}'))
                        rows = [dict(row._mapping) for row in result]
                    
                    # Convert to JSON
                    table_data = json.dumps(rows, indent=2, default=str)
                    
                    # Add to ZIP
                    zipf.writestr(f'{table_name}.json', table_data)
                except Exception as e:
                    app.logger.error(f'Error backing up table {table_name}: {str(e)}')
                    continue
            
            # Add metadata
            metadata = {
                'backup_id': backup.backup_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),  # Updated to timezone-aware
                'database_url': str(db.engine.url),
                'tables_backed_up': BACKUP_CONFIG['tables_to_backup'],
                'app_version': '1.0.0'
            }
            zipf.writestr('metadata.json', json.dumps(metadata, indent=2))
        
        # Calculate checksum
        with open(backup_file, 'rb') as f:
            file_hash = hashlib.sha256()
            while chunk := f.read(8192):
                file_hash.update(chunk)
            checksum = file_hash.hexdigest()
        
        # Encrypt the backup
        cipher_suite = Fernet(BACKUP_CONFIG['encryption_key'].encode())
        with open(backup_file, 'rb') as f:
            encrypted_data = cipher_suite.encrypt(f.read())
        
        encrypted_file = backup_file + '.enc'
        with open(encrypted_file, 'wb') as f:
            f.write(encrypted_data)
        
        # Get file size
        file_size = os.path.getsize(encrypted_file)
        
        # Store backup (local or S3)
        if s3_client:
            # Upload to S3
            s3_key = f'backups/{backup.backup_id}.zip.enc'
            s3_client.upload_file(
                encrypted_file,
                BACKUP_CONFIG['s3_bucket'],
                s3_key,
                ExtraArgs={
                    'Metadata': {
                        'backup-id': backup.backup_id,
                        'checksum': checksum,
                        'created-by': str(current_user.id)
                    }
                }
            )
            storage_location = f's3://{BACKUP_CONFIG["s3_bucket"]}/{s3_key}'
        else:
            # Store locally
            local_backup_dir = BACKUP_CONFIG['local_storage_path']
            os.makedirs(local_backup_dir, exist_ok=True)
            local_path = os.path.join(local_backup_dir, f'{backup.backup_id}.zip.enc')
            os.rename(encrypted_file, local_path)
            storage_location = local_path
        
        # Update backup record
        backup.status = 'completed'
        backup.size_bytes = file_size
        backup.storage_location = storage_location
        backup.checksum = checksum
        db.session.commit()
        
        # Clean up
        try:
            os.remove(backup_file)
            if os.path.exists(encrypted_file):
                os.remove(encrypted_file)
            os.rmdir(temp_dir)
        except:
            pass
        
    except Exception as e:
        app.logger.error(f'Backup failed: {str(e)}', exc_info=True)
        backup.status = 'failed'
        backup.notes = f'Error: {str(e)}'
        db.session.commit()

def restore_backup(backup_id):
    """Restore database from backup"""
    backup = db.session.get(BackupRecord, backup_id)
    if not backup:
        return
    
    try:
        # Get the backup file
        backup_file = get_backup_file(backup)
        if not backup_file:
            backup.status = 'failed'
            backup.notes = 'Backup file not found'
            db.session.commit()
            return
        
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        encrypted_file = os.path.join(temp_dir, 'backup.zip.enc')
        
        # Write the backup data to a temporary file
        with open(encrypted_file, 'wb') as f:
            f.write(backup_file.read())
        
        # Decrypt the backup
        cipher_suite = Fernet(BACKUP_CONFIG['encryption_key'].encode())
        with open(encrypted_file, 'rb') as f:
            decrypted_data = cipher_suite.decrypt(f.read())
        
        decrypted_file = os.path.join(temp_dir, 'backup.zip')
        with open(decrypted_file, 'wb') as f:
            f.write(decrypted_data)
        
        # Extract the ZIP file
        with zipfile.ZipFile(decrypted_file, 'r') as zipf:
            zipf.extractall(temp_dir)
        
        # Read metadata
        with open(os.path.join(temp_dir, 'metadata.json'), 'r') as f:
            metadata = json.load(f)
        
        # Restore each table using SQLAlchemy 2.0 syntax
        for table_name in metadata['tables_backed_up']:
            try:
                table_file = os.path.join(temp_dir, f'{table_name}.json')
                if not os.path.exists(table_file):
                    continue
                
                with open(table_file, 'r') as f:
                    rows = json.load(f)
                
                if not rows:
                    continue
                
                # Truncate existing table
                with db.engine.connect() as conn:
                    conn.execute(text(f'TRUNCATE TABLE {table_name} CASCADE'))
                    conn.commit()
                
                # Insert data
                with db.engine.connect() as conn:
                    for row in rows:
                        # Handle special cases (like dates)
                        for key, value in row.items():
                            if value and isinstance(value, str) and value.endswith('+00:00'):
                                try:
                                    row[key] = datetime.fromisoformat(value)
                                except:
                                    pass
                        
                        # Insert row
                        columns = ", ".join(row.keys())
                        values = ", ".join([f":{k}" for k in row.keys()])
                        conn.execute(
                            text(f'INSERT INTO {table_name} ({columns}) VALUES ({values})'),
                            row
                        )
                        conn.commit()
                
            except Exception as e:
                app.logger.error(f'Error restoring table {table_name}: {str(e)}')
                continue
        
        # Update backup record
        backup.notes = 'Restore completed successfully'
        db.session.commit()
        
        # Clean up
        try:
            os.remove(encrypted_file)
            os.remove(decrypted_file)
            for f in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, f))
            os.rmdir(temp_dir)
        except:
            pass
        
    except Exception as e:
        app.logger.error(f'Restore failed: {str(e)}', exc_info=True)
        backup.notes = f'Restore error: {str(e)}'
        db.session.commit()

def test_disaster_recovery(plan_id, backup_id):
    """Test disaster recovery plan by restoring to a test database"""
    plan = DisasterRecoveryPlan.query.get(plan_id)
    backup = BackupRecord.query.get(backup_id)
    
    if not plan or not backup:
        return
    
    try:
        # Create a test database URL by appending _test to the main DB name
        original_db_url = db.engine.url
        test_db_url = f"{original_db_url}_recovery_test"
        
        # Create a new engine for the test database
        test_engine = create_engine(test_db_url)
        
        # Create the test database if it doesn't exist
        with test_engine.connect() as conn:
            conn.execute("COMMIT")  # End any open transaction
            try:
                conn.execute(f"CREATE DATABASE {original_db_url.database}_recovery_test")
            except Exception as e:
                app.logger.info(f"Test database already exists or couldn't be created: {str(e)}")
        
        # Now connect to the test database
        test_engine.dispose()
        test_engine = create_engine(test_db_url)
        
        # Get the backup file
        backup_file = get_backup_file(backup)
        if not backup_file:
            plan.test_results = "Backup file not found"
            plan.last_tested = datetime.utcnow()
            db.session.commit()
            return
        
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        encrypted_file = os.path.join(temp_dir, 'backup.zip.enc')
        
        # Write the backup data to a temporary file
        with open(encrypted_file, 'wb') as f:
            f.write(backup_file.read())
        
        # Decrypt the backup
        cipher_suite = Fernet(BACKUP_CONFIG['encryption_key'].encode())
        with open(encrypted_file, 'rb') as f:
            decrypted_data = cipher_suite.decrypt(f.read())
        
        decrypted_file = os.path.join(temp_dir, 'backup.zip')
        with open(decrypted_file, 'wb') as f:
            f.write(decrypted_data)
        
        # Extract the ZIP file
        with zipfile.ZipFile(decrypted_file, 'r') as zipf:
            zipf.extractall(temp_dir)
        
        # Read metadata
        with open(os.path.join(temp_dir, 'metadata.json'), 'r') as f:
            metadata = json.load(f)
        
        # Restore each table to the test database
        test_metadata = {
            'tables_restored': [],
            'row_counts': {},
            'errors': []
        }
        
        for table_name in metadata['tables_backed_up']:
            try:
                table_file = os.path.join(temp_dir, f'{table_name}.json')
                if not os.path.exists(table_file):
                    continue
                
                with open(table_file, 'r') as f:
                    rows = json.load(f)
                
                if not rows:
                    continue
                
                # Truncate existing table in test database
                with test_engine.connect() as conn:
                    conn.execute(f'TRUNCATE TABLE {table_name} CASCADE')
                
                # Insert data into test database
                row_count = 0
                with test_engine.connect() as conn:
                    for row in rows:
                        # Handle special cases (like dates)
                        for key, value in row.items():
                            if value and isinstance(value, str) and value.endswith('+00:00'):
                                try:
                                    row[key] = datetime.fromisoformat(value)
                                except:
                                    pass
                        
                        # Insert row
                        conn.execute(
                            f'INSERT INTO {table_name} ({", ".join(row.keys())}) VALUES ({", ".join([f":{k}" for k in row.keys()])})',
                            **row
                        )
                        row_count += 1
                
                test_metadata['tables_restored'].append(table_name)
                test_metadata['row_counts'][table_name] = row_count
                
            except Exception as e:
                error_msg = f'Error restoring table {table_name}: {str(e)}'
                app.logger.error(error_msg)
                test_metadata['errors'].append(error_msg)
                continue
        
        # Verification Phase
        verification_results = verify_test_restoration(test_engine, metadata, test_metadata)
        
        # Combine results
        test_results = {
            'backup_id': backup.backup_id,
            'backup_timestamp': backup.timestamp.isoformat(),
            'tables_restored': len(test_metadata['tables_restored']),
            'total_rows_restored': sum(test_metadata['row_counts'].values()),
            'verification_passed': verification_results['success'],
            'verification_details': verification_results,
            'errors': test_metadata['errors']
        }
        
        # Update plan with test results
        plan.last_tested = datetime.utcnow()
        plan.test_results = json.dumps(test_results, indent=2)
        db.session.commit()
        
        # Clean up
        try:
            os.remove(encrypted_file)
            os.remove(decrypted_file)
            for f in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, f))
            os.rmdir(temp_dir)
        except:
            pass
        
    except Exception as e:
        app.logger.error(f'Disaster recovery test failed: {str(e)}', exc_info=True)
        plan.last_tested = datetime.utcnow()
        plan.test_results = f"Test failed: {str(e)}"
        db.session.commit()

def verify_test_restoration(test_engine, original_metadata, test_metadata):
    """Verify that the test restoration was successful"""
    verification = {
        'success': True,
        'checks': [],
        'table_counts': {},
        'schema_checks': {}
    }
    
    try:
        # 1. Verify all tables were restored
        with test_engine.connect() as conn:
            # Get list of tables in test database
            result = conn.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            test_tables = {row[0] for row in result}
            
            # Check against original metadata
            for table in original_metadata['tables_backed_up']:
                check = {
                    'table': table,
                    'exists': table in test_tables,
                    'row_count_match': False
                }
                
                if check['exists']:
                    # Get row count in test database
                    count = conn.execute(f'SELECT COUNT(*) FROM {table}').scalar()
                    check['test_row_count'] = count
                    check['backup_row_count'] = test_metadata['row_counts'].get(table, 0)
                    check['row_count_match'] = count == test_metadata['row_counts'].get(table, 0)
                
                verification['table_counts'][table] = check
                verification['checks'].append(f"Table {table} {'exists' if check['exists'] else 'missing'}")
                
                if not check['exists'] or not check['row_count_match']:
                    verification['success'] = False
        
        # 2. Verify schema integrity for key tables
        key_tables = ['users', 'transactions']  # Add your critical tables here
        with test_engine.connect() as conn:
            for table in key_tables:
                if table not in test_tables:
                    continue
                
                # Get column information
                result = conn.execute(f"""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = '{table}'
                """)
                columns = {row[0]: row[1] for row in result}
                
                # Check for required columns
                required_columns = {
                    'users': ['id', 'username', 'email', 'password_hash'],
                    'transactions': ['id', 'transaction_number', 'amount']
                }.get(table, [])
                
                schema_check = {
                    'columns_present': all(col in columns for col in required_columns),
                    'missing_columns': [col for col in required_columns if col not in columns],
                    'column_types': columns
                }
                
                verification['schema_checks'][table] = schema_check
                verification['checks'].append(f"Schema check for {table}: {'passed' if schema_check['columns_present'] else 'failed'}")
                
                if not schema_check['columns_present']:
                    verification['success'] = False
        
        # 3. Verify data integrity samples
        sample_verification = verify_sample_data(test_engine)
        verification['sample_checks'] = sample_verification
        verification['checks'].extend(sample_verification['checks'])
        
        if not sample_verification['success']:
            verification['success'] = False
        
        return verification
    
    except Exception as e:
        app.logger.error(f'Verification failed: {str(e)}')
        verification['success'] = False
        verification['error'] = str(e)
        return verification

def verify_sample_data(test_engine):
    """Perform sample data verification on key tables"""
    results = {
        'success': True,
        'checks': [],
        'details': {}
    }
    
    try:
        with test_engine.connect() as conn:
            # 1. Check admin user exists
            admin_count = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").scalar()
            admin_check = admin_count > 0
            results['details']['admin_user_exists'] = admin_check
            results['checks'].append(f"Admin user exists: {'yes' if admin_check else 'no'}")
            if not admin_check:
                results['success'] = False
            
            # 2. Check transaction totals match
            backup_trans_total = conn.execute("SELECT SUM(amount) FROM transactions").scalar() or 0
            results['details']['transaction_total'] = backup_trans_total
            results['checks'].append(f"Transaction total: {backup_trans_total}")
            
            # 3. Verify at least one record in each key table
            key_tables = ['users', 'transactions', 'customers', 'employees']
            for table in key_tables:
                try:
                    count = conn.execute(f"SELECT COUNT(*) FROM {table}").scalar()
                    check = count > 0
                    results['details'][f'{table}_has_data'] = check
                    results['checks'].append(f"Table {table} has data: {'yes' if check else 'no'}")
                    if not check:
                        results['success'] = False
                except:
                    results['details'][f'{table}_has_data'] = False
                    results['checks'].append(f"Table {table} check failed")
                    results['success'] = False
            
            # 4. Verify referential integrity
            ref_checks = [
                ("SELECT COUNT(*) FROM transactions t LEFT JOIN users u ON t.user_id = u.id WHERE u.id IS NULL", 'transactions.user_id -> users.id'),
                ("SELECT COUNT(*) FROM payroll p LEFT JOIN employees e ON p.employee_id = e.id WHERE e.id IS NULL", 'payroll.employee_id -> employees.id')
            ]
            
            for query, description in ref_checks:
                try:
                    bad_records = conn.execute(query).scalar()
                    check = bad_records == 0
                    results['details'][f'ref_check_{description}'] = check
                    results['checks'].append(f"Referential integrity {description}: {'valid' if check else f'{bad_records} bad records'}")
                    if not check:
                        results['success'] = False
                except:
                    results['details'][f'ref_check_{description}'] = False
                    results['checks'].append(f"Referential check failed for {description}")
                    results['success'] = False
        
        return results
    
    except Exception as e:
        app.logger.error(f'Sample data verification failed: {str(e)}')
        results['success'] = False
        results['error'] = str(e)
        return results

def verify_backup_exists(backup):
    """Verify that the backup file exists in storage"""
    if not backup.storage_location:
        return False
    
    if backup.storage_location.startswith('s3://'):
        if not s3_client:
            return False
        
        bucket, key = backup.storage_location[5:].split('/', 1)
        try:
            s3_client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False
    else:
        return os.path.exists(backup.storage_location)

def get_backup_file(backup):
    """Get the backup file from storage"""
    if not backup.storage_location:
        return None
    
    if backup.storage_location.startswith('s3://'):
        if not s3_client:
            return None
        
        bucket, key = backup.storage_location[5:].split('/', 1)
        try:
            # Create a temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            
            # Download from S3
            s3_client.download_fileobj(bucket, key, temp_file)
            temp_file.close()
            
            # Return file object
            return open(temp_file.name, 'rb')
        except ClientError as e:
            app.logger.error(f'Error downloading backup from S3: {str(e)}')
            return None
    else:
        try:
            return open(backup.storage_location, 'rb')
        except IOError as e:
            app.logger.error(f'Error opening local backup file: {str(e)}')
            return None

def delete_backup_file(backup):
    """Delete the backup file from storage"""
    if not backup.storage_location:
        return
    
    if backup.storage_location.startswith('s3://'):
        if not s3_client:
            return
        
        bucket, key = backup.storage_location[5:].split('/', 1)
        try:
            s3_client.delete_object(Bucket=bucket, Key=key)
        except ClientError as e:
            app.logger.error(f'Error deleting backup from S3: {str(e)}')
    else:
        try:
            os.remove(backup.storage_location)
        except OSError as e:
            app.logger.error(f'Error deleting local backup file: {str(e)}')


def scheduled_backup():
    """Create a scheduled backup"""
    with app.app_context():
        try:
            # Create backup record
            backup = BackupRecord(
                backup_type='scheduled',
                notes='Automated scheduled backup',
                status='in_progress'
            )
            db.session.add(backup)
            db.session.commit()
            
            # Run backup
            create_backup(backup.id)
        except Exception as e:
            app.logger.error(f'Error in scheduled backup: {str(e)}')

# Initialize scheduler
if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_backup, 'cron', hour=2, minute=0)  # Daily at 2 AM
    scheduler.start()

# ======================
# MONEY MANAGEMENT ROUTES
# ======================

@app.route('/admin/money')
@login_required
def manage_money():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    return render_template('admin/money.html',
                        drawings=Transaction.query.filter_by(transaction_type='drawing').order_by(Transaction.created_at.desc()).all(),
                        expenses=Expense.query.order_by(Expense.created_at.desc()).all(),
                        purchases=Purchase.query.order_by(Purchase.created_at.desc()).all(),
                        payroll=Payroll.query.order_by(Payroll.created_at.desc()).all(),
                        debtors=Debtor.query.order_by(Debtor.amount_owed.desc()).all(),
                        employees=Employee.query.all(),
                        customers=Customer.query.all(),
                        current_date=datetime.utcnow().date())

# ==============
# DRAWING ROUTES
# ==============

@app.route('/admin/add_drawing', methods=['POST'])
@login_required
def add_drawing():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        amount = float(request.form.get('amount'))
        description = request.form.get('description')
        
        transaction = Transaction(
            transaction_number=generate_transaction_number(),
            transaction_type='drawing',  # Changed from 'expense' to 'drawing'
            amount=amount,
            user_id=current_user.id,
            notes=f"Owner's drawing: {description}"
        )
        db.session.add(transaction)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Drawing added successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/admin/update_drawing/<int:id>', methods=['POST'])
@login_required
def update_drawing(id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    drawing = Transaction.query.get_or_404(id)
    try:
        drawing.amount = float(request.form.get('amount'))
        drawing.notes = request.form.get('description')
        db.session.commit()
        flash('Drawing updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating drawing: {str(e)}', 'danger')
    return redirect(url_for('manage_money'))

@app.route('/admin/delete_drawing/<int:id>', methods=['POST'])
@login_required
def delete_drawing(id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    drawing = Transaction.query.get_or_404(id)
    try:
        db.session.delete(drawing)
        db.session.commit()
        flash('Drawing deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting drawing: {str(e)}', 'danger')
    return redirect(url_for('manage_money'))

# =============
# BILLS ROUTES
# =============

@app.route('/admin/add_bill', methods=['POST'])
@login_required
def add_bill():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        expense = Expense(
            expense_number=generate_expense_number(),
            expense_type=request.form.get('bill_type'),
            amount=float(request.form.get('amount')),
            user_id=current_user.id,
            description=request.form.get('description'),
            due_date=datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date(),
            status='pending'
        )
        db.session.add(expense)
        db.session.commit()
        flash('Bill added successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding bill: {str(e)}', 'danger')
    return redirect(url_for('manage_money'))

@app.route('/admin/update_bill/<int:id>', methods=['POST'])
@login_required
def update_bill(id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    bill = Expense.query.get_or_404(id)
    try:
        bill.expense_type = request.form.get('bill_type')
        bill.amount = float(request.form.get('amount'))
        bill.description = request.form.get('description')
        bill.due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date()
        db.session.commit()
        flash('Bill updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating bill: {str(e)}', 'danger')
    return redirect(url_for('manage_money'))

@app.route('/admin/delete_bill/<int:id>', methods=['POST'])
@login_required
def delete_bill(id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    bill = Expense.query.get_or_404(id)
    try:
        db.session.delete(bill)
        db.session.commit()
        flash('Bill deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting bill: {str(e)}', 'danger')
    return redirect(url_for('manage_money'))

@app.route('/admin/pay_bill/<int:id>', methods=['POST'])
@login_required
def pay_bill(id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    bill = Expense.query.get_or_404(id)
    try:
        bill.status = 'paid'
        bill.paid_date = datetime.utcnow().date()
        
        transaction = Transaction(
            transaction_number=generate_transaction_number(),
            transaction_type='expense',
            amount=bill.amount,
            user_id=current_user.id,
            reference_id=bill.id,
            notes=f"Bill payment: {bill.expense_type}"
        )
        db.session.add(transaction)
        db.session.commit()
        flash('Bill payment recorded successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error paying bill: {str(e)}', 'danger')
    return redirect(url_for('manage_money'))

# ================
# PURCHASE ROUTES
# ================

@app.route('/admin/add_purchase', methods=['POST'])
@login_required
def add_purchase():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        purchase = Purchase(
            purchase_number=generate_purchase_number(),
            purchase_type=request.form.get('purchase_type'),
            amount=float(request.form.get('amount')),
            purchase_date=datetime.strptime(request.form.get('purchase_date'), '%Y-%m-%d').date(),
            supplier=request.form.get('supplier'),
            description=request.form.get('description'),
            user_id=current_user.id
        )
        db.session.add(purchase)
        
        transaction = Transaction(
            transaction_number=generate_transaction_number(),
            transaction_type='expense',
            amount=float(request.form.get('amount')),
            user_id=current_user.id,
            reference_id=purchase.id,
            notes=f"Purchase: {purchase.purchase_type}"
        )
        db.session.add(transaction)
        db.session.commit()
        flash('Purchase added successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding purchase: {str(e)}', 'danger')
    return redirect(url_for('manage_money'))

@app.route('/admin/update_purchase/<int:id>', methods=['POST'])
@login_required
def update_purchase(id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    purchase = Purchase.query.get_or_404(id)
    try:
        purchase.purchase_type = request.form.get('purchase_type')
        purchase.amount = float(request.form.get('amount'))
        purchase.purchase_date = datetime.strptime(request.form.get('purchase_date'), '%Y-%m-%d').date()
        purchase.supplier = request.form.get('supplier')
        purchase.description = request.form.get('description')
        db.session.commit()
        flash('Purchase updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating purchase: {str(e)}', 'danger')
    return redirect(url_for('manage_money'))

@app.route('/admin/delete_purchase/<int:id>', methods=['POST'])
@login_required
def delete_purchase(id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    purchase = Purchase.query.get_or_404(id)
    try:
        # Delete associated transaction first
        Transaction.query.filter_by(transaction_type='purchase', reference_id=id).delete()
        db.session.delete(purchase)
        db.session.commit()
        flash('Purchase deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting purchase: {str(e)}', 'danger')
    return redirect(url_for('manage_money'))
# ===============
# PAYROLL ROUTES
# ===============

@app.route('/admin/add_payroll', methods=['POST'])
@login_required
def add_payroll():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('manage_money'))

    try:
        # Validate required fields
        if not all([request.form.get('employee_id'), request.form.get('amount'), request.form.get('payment_date')]):
            flash('Please fill all required fields', 'danger')
            return redirect(url_for('manage_money'))

        employee = db.session.get(Employee, request.form.get('employee_id'))
        if not employee:
            flash('Employee not found', 'danger')
            return redirect(url_for('manage_money'))

        amount = float(request.form.get('amount'))
        if amount <= 0:
            flash('Amount must be positive', 'danger')
            return redirect(url_for('manage_money'))

        payment_date = datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date()
        
        payroll = Payroll(
            payroll_number=generate_payroll_number(),
            employee_id=employee.id,
            amount=amount,
            payment_date=payment_date,
            pay_period=request.form.get('pay_period', 'monthly'),
            notes=request.form.get('notes', ''),
            status='paid',  # Assuming immediate payment
            user_id=current_user.id
        )
        db.session.add(payroll)
        
        # Create transaction record
        transaction = Transaction(
            transaction_number=generate_transaction_number(),
            transaction_type='expense',
            amount=amount,
            user_id=current_user.id,
            reference_id=payroll.id,
            notes=f"Payroll payment for {employee.name}",
            created_at=datetime.utcnow()  # Using created_at instead of date
        )
        db.session.add(transaction)
        
        db.session.commit()
        flash('Payroll payment added successfully', 'success')
    except ValueError as e:
        db.session.rollback()
        flash(f'Invalid data format: {str(e)}', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding payroll: {str(e)}', 'danger')
    
    return redirect(url_for('manage_money'))

@app.route('/admin/update_payroll/<int:id>', methods=['POST'])
@login_required
def update_payroll(id):
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('manage_money'))

    payroll = Payroll.query.get_or_404(id)
    try:
        if not all([request.form.get('employee_id'), request.form.get('amount'), request.form.get('payment_date')]):
            flash('Please fill all required fields', 'danger')
            return redirect(url_for('manage_money'))

        employee = Employee.query.get(request.form.get('employee_id'))
        if not employee:
            flash('Employee not found', 'danger')
            return redirect(url_for('manage_money'))

        amount = float(request.form.get('amount'))
        if amount <= 0:
            flash('Amount must be positive', 'danger')
            return redirect(url_for('manage_money'))

        # Update payroll
        payroll.employee_id = employee.id
        payroll.amount = amount
        payroll.payment_date = datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date()
        payroll.pay_period = request.form.get('pay_period', payroll.pay_period)
        payroll.notes = request.form.get('notes', payroll.notes)
        
        # Update associated transaction
        transaction = Transaction.query.filter_by(transaction_type='payroll', reference_id=id).first()
        if transaction:
            transaction.amount = amount
            transaction.notes = f"Payroll payment for {employee.name}"
            transaction.created_at = datetime.utcnow()
        
        db.session.commit()
        flash('Payroll updated successfully', 'success')
    except ValueError as e:
        db.session.rollback()
        flash(f'Invalid data format: {str(e)}', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating payroll: {str(e)}', 'danger')
    
    return redirect(url_for('manage_money'))

@app.route('/admin/delete_payroll/<int:id>', methods=['POST'])
@login_required
def delete_payroll(id):
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('manage_money'))

    payroll = Payroll.query.get_or_404(id)
    try:
        # Delete associated transaction
        Transaction.query.filter_by(transaction_type='payroll', reference_id=id).delete()
        
        # Delete payroll
        db.session.delete(payroll)
        db.session.commit()
        flash('Payroll deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting payroll: {str(e)}', 'danger')
    
    return redirect(url_for('manage_money'))

# ================
# DEBTOR ROUTES
# ================
@app.route('/admin/add_debtor', methods=['POST'])
@login_required
def add_debtor():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('manage_money'))

    try:
        # Validate required fields
        if not all([request.form.get('name'), request.form.get('total_debt')]):
            flash('Name and total debt are required', 'danger')
            return redirect(url_for('manage_money'))

        total_debt = float(request.form.get('total_debt'))
        if total_debt <= 0:
            flash('Total debt must be positive', 'danger')
            return redirect(url_for('manage_money'))

        # Create new debtor
        debtor = Debtor(
            name=request.form.get('name'),
            contact=request.form.get('contact', ''),
            email=request.form.get('email', ''),
            Total_debt=total_debt,
            amount_paid=0.0,  # Initialize with 0
            amount_owed=total_debt,  # Initially equals total debt
            last_payment_date=datetime.strptime(request.form.get('last_payment_date'), '%Y-%m-%d').date() if request.form.get('last_payment_date') else None,
        )
        
        db.session.add(debtor)
        db.session.commit()
        flash('Debtor added successfully', 'success')
    except ValueError:
        db.session.rollback()
        flash('Invalid amount format', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding debtor: {str(e)}', 'danger')
    
    return redirect(url_for('manage_money'))

@app.route('/admin/add_debtor_payment/<int:debtor_id>', methods=['POST'])
@login_required
def add_debtor_payment(id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    debtor = Debtor.query.get_or_404(id)
    try:
        if not all([request.form.get('amount'), request.form.get('payment_date')]):
            return jsonify({'error': 'Amount and payment date are required'}), 400

        payment_amount = float(request.form.get('amount'))
        if payment_amount <= 0:
            return jsonify({'error': 'Payment amount must be positive'}), 400

        if payment_amount > debtor.amount_owed:
            return jsonify({'error': 'Payment amount exceeds owed amount'}), 400

        payment_date = datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date()
        
        # Update debtor records
        debtor.amount_paid += payment_amount
        debtor.amount_owed = debtor.Total_debt - debtor.amount_paid
        debtor.last_payment_date = payment_date
        
        # Create payment record
        payment = DebtorPayment(
            id=id,
            amount=payment_amount,
            payment_date=payment_date,
            payment_method=request.form.get('payment_method', 'cash'),
            notes=request.form.get('notes', ''),
            user_id=current_user.id
        )
        db.session.add(payment)
        
        # Create transaction record
        transaction = Transaction(
            transaction_number=generate_transaction_number(),
            transaction_type='income',
            amount=payment_amount,
            user_id=current_user.id,
            reference_id=payment.id,
            notes=f"Payment from {debtor.name}",
            created_at=datetime.utcnow()
        )
        db.session.add(transaction)
        
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Payment recorded successfully',
            'amount_paid': debtor.amount_paid,
            'amount_owed': debtor.amount_owed
        })
    except ValueError:
        db.session.rollback()
        return jsonify({'error': 'Invalid amount or date format'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/update_debtor/<int:id>', methods=['POST'])
def update_debtor(id):
    debtor = Debtor.query.get_or_404(id)
    try:
        debtor.name = request.form.get('name')
        debtor.contact = request.form.get('contact', debtor.contact)
        debtor.email = request.form.get('email', debtor.email)
        debtor.Total_debt = float(request.form.get('total_debt'))
        debtor.amount_owed = debtor.Total_debt - debtor.amount_paid
        debtor.balance = debtor.amount_owed  # If using Option 1
        db.session.commit()
        flash('Debtor updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating debtor: {str(e)}', 'danger')
    return redirect(url_for('manage_money'))


@app.route('/admin/delete_debtor/<int:id>', methods=['POST'])
@login_required
def delete_debtor(id):
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('manage_money'))

    debtor = Debtor.query.get_or_404(id)
    try:
        # Only delete the debtor, payments and transactions remain
        db.session.delete(debtor)
        db.session.commit()
        flash('Debtor deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting debtor: {str(e)}', 'danger')
    
    return redirect(url_for('manage_money'))
    
# =====================
# TRANSACTION ROUTES
# =====================

@app.route('/admin/delete_transaction/<int:id>', methods=['POST'])
@login_required
def delete_transaction(id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    transaction = Transaction.query.get_or_404(id)
    try:
        # Handle different transaction types
        if transaction.transaction_type == 'purchase':
            Purchase.query.filter_by(id=transaction.reference_id).delete()
        elif transaction.transaction_type == 'payroll':
            Payroll.query.filter_by(id=transaction.reference_id).delete()
        elif transaction.transaction_type == 'debtor_payment':
            DebtorPayment.query.filter_by(id=transaction.reference_id).delete()
        
        db.session.delete(transaction)
        db.session.commit()
        flash('Transaction deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting transaction: {str(e)}', 'danger')
    return redirect(url_for('manage_money'))

# ========================
# PENDING PAYMENTS CHECK
# =======================
@app.route('/admin/check_pending_payments')
@login_required
def check_pending_payments():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    today = datetime.utcnow().date()
    
    # Pending bills (status is pending and due date is today or passed)
    pending_bills = Expense.query.filter(
        Expense.status == 'pending',
        Expense.due_date <= today
    ).count()
    
    # Pending payroll (payment date is today or passed)
    pending_payroll = Payroll.query.filter(
        Payroll.payment_date <= today
    ).count()
    
    # Pending debtor payments (next payment date is today or passed)
    pending_debtor_payments = Debtor.query.filter(
        Debtor.next_payment_date <= today
    ).count()
    
    total_pending = pending_bills + pending_payroll + pending_debtor_payments
    
    return jsonify({
        'count': total_pending,
        'pending_bills': pending_bills,
        'pending_payroll': pending_payroll,
        'pending_debtor_payments': pending_debtor_payments
    })
@app.route('/admin/money/summary')
@login_required
def money_summary():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Calculate totals
        total_income = db.session.query(
            func.sum(Transaction.amount)
        ).filter(
            Transaction.transaction_type == 'income'
        ).scalar() or 0

        total_expenses = db.session.query(
            func.sum(Transaction.amount)
        ).filter(
            Transaction.transaction_type.in_(['expense', 'drawing', 'purchase', 'payroll'])
        ).scalar() or 0

        net_profit = total_income - total_expenses
        
        return jsonify({
            'total_income': float(total_income),
            'total_expenses': float(total_expenses),
            'net_profit': float(net_profit),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/admin/dosage', methods=['GET', 'POST'])
@login_required
def manage_dosage():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            try:
                dosage = DrugDosage(
                    drug_id=request.form.get('drug_id'),
                    indication=request.form.get('indication'),
                    contraindication=request.form.get('contraindication'),
                    interaction=request.form.get('interaction'),
                    side_effects=request.form.get('side_effects'),
                    dosage_peds=request.form.get('dosage_peds'),
                    dosage_adults=request.form.get('dosage_adults'),
                    dosage_geriatrics=request.form.get('dosage_geriatrics'),
                    important_notes=request.form.get('important_notes')
                )
                db.session.add(dosage)
                db.session.commit()
                
                log_audit('create', 'DrugDosage', dosage.id, None, {
                    'drug_id': dosage.drug_id,
                    'indication': dosage.indication,
                    'contraindication': dosage.contraindication,
                    'interaction': dosage.interaction,
                    'side_effects': dosage.side_effects,
                    'dosage_peds': dosage.dosage_peds,
                    'dosage_adults': dosage.dosage_adults,
                    'dosage_geriatrics': dosage.dosage_geriatrics,
                    'important_notes': dosage.important_notes
                })
                
                flash('Dosage information added successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding dosage information: {str(e)}', 'danger')
        
        elif action == 'edit':
            dosage_id = request.form.get('dosage_id')
            dosage = DrugDosage.query.get(dosage_id)
            if dosage:
                try:
                    old_values = {
                        'drug_id': dosage.drug_id,
                        'indication': dosage.indication,
                        'contraindication': dosage.contraindication,
                        'interaction': dosage.interaction,
                        'side_effects': dosage.side_effects,
                        'dosage_peds': dosage.dosage_peds,
                        'dosage_adults': dosage.dosage_adults,
                        'dosage_geriatrics': dosage.dosage_geriatrics,
                        'important_notes': dosage.important_notes
                    }
                    
                    dosage.indication = request.form.get('indication')
                    dosage.contraindication = request.form.get('contraindication')
                    dosage.interaction = request.form.get('interaction')
                    dosage.side_effects = request.form.get('side_effects')
                    dosage.dosage_peds = request.form.get('dosage_peds')
                    dosage.dosage_adults = request.form.get('dosage_adults')
                    dosage.dosage_geriatrics = request.form.get('dosage_geriatrics')
                    dosage.important_notes = request.form.get('important_notes')
                    
                    db.session.commit()
                    
                    log_audit('update', 'DrugDosage', dosage.id, old_values, {
                        'drug_id': dosage.drug_id,
                        'indication': dosage.indication,
                        'contraindication': dosage.contraindication,
                        'interaction': dosage.interaction,
                        'side_effects': dosage.side_effects,
                        'dosage_peds': dosage.dosage_peds,
                        'dosage_adults': dosage.dosage_adults,
                        'dosage_geriatrics': dosage.dosage_geriatrics,
                        'important_notes': dosage.important_notes
                    })
                    
                    flash('Dosage information updated successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error updating dosage information: {str(e)}', 'danger')
            else:
                flash('Dosage information not found', 'danger')
        
        elif action == 'delete':
            dosage_id = request.form.get('dosage_id')
            dosage = DrugDosage.query.get(dosage_id)
            if dosage:
                try:
                    log_audit('delete', 'DrugDosage', dosage.id, {
                        'drug_id': dosage.drug_id,
                        'indication': dosage.indication,
                        'contraindication': dosage.contraindication,
                        'interaction': dosage.interaction,
                        'side_effects': dosage.side_effects,
                        'dosage_peds': dosage.dosage_peds,
                        'dosage_adults': dosage.dosage_adults,
                        'dosage_geriatrics': dosage.dosage_geriatrics,
                        'important_notes': dosage.important_notes
                    }, None)
                    
                    db.session.delete(dosage)
                    db.session.commit()
                    flash('Dosage information deleted successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error deleting dosage information: {str(e)}', 'danger')
            else:
                flash('Dosage information not found', 'danger')
        
        return redirect(url_for('manage_dosage'))
    
    dosages = DrugDosage.query.join(Drug).all()
    drugs = Drug.query.all()
    
    return render_template('admin/dosage.html', dosages=dosages, drugs=drugs)

@app.route('/admin/dosage/<int:dosage_id>')
@login_required
def get_dosage(dosage_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    dosage = DrugDosage.query.get_or_404(dosage_id)
    
    return jsonify({
        'id': dosage.id,
        'drug': {
            'id': dosage.drug.id,
            'drug_number': dosage.drug.drug_number,
            'name': dosage.drug.name
        },
        'indication': dosage.indication,
        'contraindication': dosage.contraindication,
        'interaction': dosage.interaction,
        'side_effects': dosage.side_effects,
        'dosage_peds': dosage.dosage_peds,
        'dosage_adults': dosage.dosage_adults,
        'dosage_geriatrics': dosage.dosage_geriatrics,
        'important_notes': dosage.important_notes
    })

@app.route('/admin/drugs/without-dosage')
@login_required
def get_drugs_without_dosage():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get drugs that don't have dosage information
    drugs = Drug.query.filter(~Drug.dosage.any()).all()
    
    return jsonify([{
        'id': drug.id,
        'drug_number': drug.drug_number,
        'name': drug.name
    } for drug in drugs])

@app.route('/admin/drugs/<int:drug_id>/dosage')
@login_required
def get_drug_dosage(drug_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    drug = Drug.query.get_or_404(drug_id)
    dosage = DrugDosage.query.filter_by(drug_id=drug.id).first()
    
    return jsonify({
        'drug': {
            'id': drug.id,
            'name': drug.name,
            'drug_number': drug.drug_number
        },
        'dosage': {
            'indication': dosage.indication if dosage else None,
            'contraindication': dosage.contraindication if dosage else None,
            'interaction': dosage.interaction if dosage else None,
            'side_effects': dosage.side_effects if dosage else None,
            'dosage_peds': dosage.dosage_peds if dosage else None,
            'dosage_adults': dosage.dosage_adults if dosage else None,
            'dosage_geriatrics': dosage.dosage_geriatrics if dosage else None,
            'important_notes': dosage.important_notes if dosage else None
        } if dosage else None
    })

# Admin Patient Management Routes
@app.route('/admin/patients', methods=['GET', 'POST'])
@login_required
def manage_patients():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    # Handle date filtering
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = Patient.query
    
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Patient.created_at >= start_date)
        except ValueError:
            flash('Invalid start date format', 'danger')
    
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Patient.created_at <= end_date)
        except ValueError:
            flash('Invalid end date format', 'danger')
    
    patients = query.order_by(Patient.created_at.desc()).all()
    
    # Calculate summary totals
    total_lab_amount = 0
    total_service_amount = 0
    total_drug_amount = 0
    
    for patient in patients:
        # Lab tests total
        for lab in patient.labs:
            total_lab_amount += lab.test.price
        
        # Services total (assuming you have a PatientService model)
        for service in patient.services:
            total_service_amount += service.service.price
        
        # Prescriptions total
        for prescription in patient.prescriptions:
            for item in prescription.items:
                total_drug_amount += item.drug.selling_price * item.quantity
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            try:
                patient_type = request.form.get('patient_type')
                patient_number = generate_patient_number(patient_type)
                
                patient = Patient(
                    op_number=patient_number if patient_type == 'OP' else None,
                    ip_number=patient_number if patient_type == 'IP' else None,
                    name=Config.encrypt_data_static(request.form.get('name')),
                    age=int(request.form.get('age')) if request.form.get('age') else None,
                    gender=request.form.get('gender'),
                    address=Config.encrypt_data_static(request.form.get('address')) if request.form.get('address') else None,
                    phone=Config.encrypt_data_static(request.form.get('phone')) if request.form.get('phone') else None,
                    nok_name=Config.encrypt_data_static(request.form.get('nok_name')) if request.form.get('nok_name') else None,
                    nok_contact=Config.encrypt_data_static(request.form.get('nok_contact')) if request.form.get('nok_contact') else None,
                    chief_complaints=request.form.get('chief_complaints'),
                    diagnosis=request.form.get('diagnosis'),
                    tca=datetime.strptime(request.form.get('tca'), '%Y-%m-%d').date() if request.form.get('tca') else None,
                    status='active'
                )
                db.session.add(patient)
                db.session.commit()
                
                log_audit('create', 'Patient', patient.id, None, {
                    'patient_number': patient_number,
                    'name': request.form.get('name'),
                    'age': request.form.get('age'),
                    'gender': request.form.get('gender')
                })
                
                flash('Patient added successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding patient: {str(e)}', 'danger')
        
        elif action == 'edit':
            patient_id = request.form.get('patient_id')
            patient = Patient.query.get(patient_id)
            if patient:
                try:
                    old_values = {
                        'name': Config.decrypt_data_static(patient.name),
                        'age': patient.age,
                        'gender': patient.gender,
                        'address': Config.decrypt_data_static(patient.address),
                        'phone': Config.decrypt_data_static(patient.phone),
                        'nok_name': Config.decrypt_data_static(patient.nok_name),
                        'nok_contact': Config.decrypt_data_static(patient.nok_contact),
                        'chief_complaints': patient.chief_complaints,
                        'diagnosis': patient.diagnosis,
                        'tca': patient.tca,
                        'status': patient.status
                    }
                    
                    patient.name = Config.encrypt_data_static(request.form.get('name'))
                    patient.age = int(request.form.get('age')) if request.form.get('age') else None
                    patient.gender = request.form.get('gender')
                    patient.address = Config.encrypt_data_static(request.form.get('address')) if request.form.get('address') else None
                    patient.phone = Config.encrypt_data_static(request.form.get('phone')) if request.form.get('phone') else None
                    patient.nok_name = Config.encrypt_data_static(request.form.get('nok_name')) if request.form.get('nok_name') else None
                    patient.nok_contact = Config.encrypt_data_static(request.form.get('nok_contact')) if request.form.get('nok_contact') else None
                    patient.chief_complaints = request.form.get('chief_complaints')
                    patient.diagnosis = request.form.get('diagnosis')
                    patient.tca = datetime.strptime(request.form.get('tca'), '%Y-%m-%d').date() if request.form.get('tca') else None
                    patient.status = request.form.get('status')
                    
                    db.session.commit()
                    
                    log_audit('update', 'Patient', patient.id, old_values, {
                        'name': request.form.get('name'),
                        'age': request.form.get('age'),
                        'gender': request.form.get('gender'),
                        'address': request.form.get('address'),
                        'phone': request.form.get('phone'),
                        'nok_name': request.form.get('nok_name'),
                        'nok_contact': request.form.get('nok_contact'),
                        'chief_complaints': request.form.get('chief_complaints'),
                        'diagnosis': request.form.get('diagnosis'),
                        'tca': request.form.get('tca'),
                        'status': request.form.get('status')
                    })
                    
                    flash('Patient updated successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error updating patient: {str(e)}', 'danger')
            else:
                flash('Patient not found', 'danger')
        
        return redirect(url_for('manage_patients'))
    
    lab_tests = LabTest.query.all()
    services = Service.query.all()
    
    return render_template('admin/patients.html',
        patients=patients,
        lab_tests=lab_tests,
        services=services,
        total_lab_amount=total_lab_amount,
        total_service_amount=total_service_amount,
        total_drug_amount=total_drug_amount,
        total_amount=total_lab_amount + total_service_amount + total_drug_amount
    )

@app.route('/admin/patients/<int:patient_id>')
@login_required
def get_patient(patient_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    patient = Patient.query.get_or_404(patient_id)
    
    return jsonify({
        'id': patient.id,
        'op_number': patient.op_number,
        'ip_number': patient.ip_number,
        'name': Config.decrypt_data_static(patient.name),
        'age': patient.age,
        'gender': patient.gender,
        'address': Config.decrypt_data_static(patient.address),
        'phone': Config.decrypt_data_static(patient.phone),
        'nok_name': Config.decrypt_data_static(patient.nok_name),
        'nok_contact': Config.decrypt_data_static(patient.nok_contact),
        'chief_complaints': patient.chief_complaints,
        'diagnosis': patient.diagnosis,
        'tca': patient.tca.strftime('%Y-%m-%d') if patient.tca else None,
        'status': patient.status
    })

@app.route('/admin/patients/<int:patient_id>/details')
@login_required
def patient_details(patient_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    patient = Patient.query.get_or_404(patient_id)
    
    # Calculate financial totals
    total_lab_amount = sum(lab.test.price for lab in patient.labs)
    total_service_amount = sum(service.service.price for service in patient.services)
    total_drug_amount = sum(
        item.drug.selling_price * item.quantity 
        for prescription in patient.prescriptions 
        for item in prescription.items
    )
    
    return jsonify({
        'patient_number': patient.op_number or patient.ip_number,
        'name': Config.decrypt_data_static(patient.name),
        'age': patient.age,
        'gender': patient.gender,
        'type': 'OP' if patient.op_number else 'IP',
        'address': Config.decrypt_data_static(patient.address),
        'phone': Config.decrypt_data_static(patient.phone),
        'nok_name': Config.decrypt_data_static(patient.nok_name),
        'nok_contact': Config.decrypt_data_static(patient.nok_contact),
        'complaints': patient.chief_complaints,
        'diagnosis': patient.diagnosis,
        'treatment': patient.treatment,
        'tca': patient.tca.strftime('%Y-%m-%d') if patient.tca else None,
        'status': patient.status,
        'total_lab_amount': total_lab_amount,
        'total_service_amount': total_service_amount,
        'total_drug_amount': total_drug_amount,
        'total_amount': total_lab_amount + total_service_amount + total_drug_amount,
        'lab_tests': [{
            'id': lab.id,
            'name': lab.test.name,
            'price': lab.test.price,
            'results': lab.results,
            'comments': lab.comments,
            'date': lab.created_at.strftime('%Y-%m-%d')
        } for lab in patient.labs],
        'services': [{
            'id': service.id,
            'name': service.service.name,
            'price': service.service.price,
            'notes': service.notes,
            'date': service.created_at.strftime('%Y-%m-%d')
        } for service in patient.services],
        'prescriptions': [{
            'id': item.id,
            'drug_name': item.drug.name,
            'quantity': item.quantity,
            'unit_price': item.drug.selling_price,
            'status': item.status,
            'date': prescription.created_at.strftime('%Y-%m-%d')
        } for prescription in patient.prescriptions for item in prescription.items]
    })
# Medical Tests Management
@app.route('/admin/medical-tests')
@login_required
def manage_medical_tests():
    if current_user.role != 'admin':
        abort(403)
    
    services = Service.query.order_by(Service.name).all()
    lab_tests = LabTest.query.order_by(LabTest.name).all()
    imaging_tests = ImagingTest.query.order_by(ImagingTest.name).all()
    
    return render_template('admin/medical_tests.html', 
                         services=services,
                         lab_tests=lab_tests,
                         imaging_tests=imaging_tests)

# Service CRUD
@app.route('/admin/services/add', methods=['POST'])
@login_required
def add_service():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        service = Service(
            name=request.form.get('name'),
            price=float(request.form.get('price')),
            description=request.form.get('description')
        )
        db.session.add(service)
        db.session.commit()
        
        log_audit('add_service', 'Service', service.id, None, {
            'name': service.name,
            'price': service.price
        })
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/services/<int:id>')
@login_required
def get_service(id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    service = Service.query.get_or_404(id)
    return jsonify({
        'id': service.id,
        'name': service.name,
        'price': service.price,
        'description': service.description
    })

@app.route('/admin/services/<int:id>/update', methods=['POST'])
@login_required
def update_service(id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    service = Service.query.get_or_404(id)
    
    try:
        old_data = {
            'name': service.name,
            'price': service.price,
            'description': service.description
        }
        
        service.name = request.form.get('name')
        service.price = float(request.form.get('price'))
        service.description = request.form.get('description')
        
        db.session.commit()
        
        log_audit('update_service', 'Service', service.id, old_data, {
            'name': service.name,
            'price': service.price,
            'description': service.description
        })
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/services/<int:id>/delete', methods=['POST'])
@login_required
def delete_service(id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    service = Service.query.get_or_404(id)
    
    try:
        log_audit('delete_service', 'Service', service.id, {
            'name': service.name,
            'price': service.price
        }, None)
        
        db.session.delete(service)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Lab Test CRUD
@app.route('/admin/lab-tests/add', methods=['POST'])
@login_required
def add_lab_test():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        lab_test = LabTest(
            name=request.form.get('name'),
            price=float(request.form.get('price')),
            description=request.form.get('description')
        )
        db.session.add(lab_test)
        db.session.commit()
        
        log_audit('add_lab_test', 'LabTest', lab_test.id, None, {
            'name': lab_test.name,
            'price': lab_test.price
        })
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/lab-tests/<int:id>')
@login_required
def get_lab_test(id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    lab_test = LabTest.query.get_or_404(id)
    return jsonify({
        'id': lab_test.id,
        'name': lab_test.name,
        'price': lab_test.price,
        'description': lab_test.description
    })

@app.route('/admin/lab-tests/<int:id>/update', methods=['POST'])
@login_required
def update_lab_test(id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    lab_test = LabTest.query.get_or_404(id)
    
    try:
        old_data = {
            'name': lab_test.name,
            'price': lab_test.price,
            'description': lab_test.description
        }
        
        lab_test.name = request.form.get('name')
        lab_test.price = float(request.form.get('price'))
        lab_test.description = request.form.get('description')
        
        db.session.commit()
        
        log_audit('update_lab_test', 'LabTest', lab_test.id, old_data, {
            'name': lab_test.name,
            'price': lab_test.price,
            'description': lab_test.description
        })
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/lab-tests/<int:id>/delete', methods=['POST'])
@login_required
def delete_lab_test(id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    lab_test = LabTest.query.get_or_404(id)
    
    try:
        log_audit('delete_lab_test', 'LabTest', lab_test.id, {
            'name': lab_test.name,
            'price': lab_test.price
        }, None)
        
        db.session.delete(lab_test)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Imaging Test CRUD
@app.route('/admin/imaging-tests/add', methods=['POST'])
@login_required
def add_imaging_test():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        imaging_test = ImagingTest(
            name=request.form.get('name'),
            price=float(request.form.get('price')),
            description=request.form.get('description'),
            is_active=request.form.get('is_active') == 'on'
        )
        db.session.add(imaging_test)
        db.session.commit()
        
        log_audit('add_imaging_test', 'ImagingTest', imaging_test.id, None, {
            'name': imaging_test.name,
            'price': imaging_test.price,
            'is_active': imaging_test.is_active
        })
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/imaging-tests/<int:id>')
@login_required
def get_imaging_test(id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    imaging_test = ImagingTest.query.get_or_404(id)
    return jsonify({
        'id': imaging_test.id,
        'name': imaging_test.name,
        'price': imaging_test.price,
        'description': imaging_test.description,
        'is_active': imaging_test.is_active
    })

@app.route('/admin/imaging-tests/<int:id>/update', methods=['POST'])
@login_required
def update_imaging_test(id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    imaging_test = ImagingTest.query.get_or_404(id)
    
    try:
        old_data = {
            'name': imaging_test.name,
            'price': imaging_test.price,
            'description': imaging_test.description,
            'is_active': imaging_test.is_active
        }
        
        imaging_test.name = request.form.get('name')
        imaging_test.price = float(request.form.get('price'))
        imaging_test.description = request.form.get('description')
        imaging_test.is_active = request.form.get('is_active') == 'on'
        
        db.session.commit()
        
        log_audit('update_imaging_test', 'ImagingTest', imaging_test.id, old_data, {
            'name': imaging_test.name,
            'price': imaging_test.price,
            'description': imaging_test.description,
            'is_active': imaging_test.is_active
        })
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/imaging-tests/<int:id>/delete', methods=['POST'])
@login_required
def delete_imaging_test(id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    imaging_test = ImagingTest.query.get_or_404(id)
    
    try:
        log_audit('delete_imaging_test', 'ImagingTest', imaging_test.id, {
            'name': imaging_test.name,
            'price': imaging_test.price
        }, None)
        
        db.session.delete(imaging_test)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/pharmacist')
@login_required
def pharmacist_dashboard():
    try:
        if current_user.role != 'pharmacist':
            flash('Unauthorized access', 'danger')
            return redirect(url_for('home'))
        
        # Get counts for dashboard cards
        low_stock = Drug.query.filter(Drug.remaining_quantity < 10).count()
        expiring_soon = Drug.query.filter(
            Drug.expiry_date <= date.today() + timedelta(days=30),
            Drug.expiry_date >= date.today()
        ).count()
        
        # Get recent sales (last 5)
        recent_sales = Sale.query.order_by(Sale.created_at.desc()).limit(5).all()
        
        # Get pending prescriptions count
        pending_prescriptions = Prescription.query.filter_by(status='pending').count()
        
        return render_template('pharmacist/dashboard.html',
            low_stock=low_stock,
            expiring_soon=expiring_soon,
            recent_sales=recent_sales,
            pending_prescriptions=pending_prescriptions
        )
    except Exception as e:
        current_app.logger.error(f"Error in pharmacist_dashboard: {str(e)}")
        flash('An error occurred while loading the dashboard', 'danger')
        return redirect(url_for('home'))

@app.route('/pharmacist/drugs')
@login_required
def pharmacist_drugs():
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get filter parameters
    filter_type = request.args.get('filter', 'all')
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort', 'name_asc')
    
    # Base query
    query = Drug.query
    
    # Apply filters
    if filter_type == 'low':
        query = query.filter(Drug.remaining_quantity < 10)
    elif filter_type == 'out':
        query = query.filter(Drug.remaining_quantity == 0)
    elif filter_type == 'expiring':
        query = query.filter(Drug.expiry_date <= date.today() + timedelta(days=30))
    
    # Apply search
    if search_query:
        query = query.filter(
            or_(
                Drug.name.ilike(f'%{search_query}%'),
                Drug.drug_number.ilike(f'%{search_query}%'),
            )
        )
    
    # Apply sorting
    if sort_by == 'name_asc':
        query = query.order_by(Drug.name.asc())
    elif sort_by == 'name_desc':
        query = query.order_by(Drug.name.desc())
    elif sort_by == 'stock_asc':
        query = query.order_by(Drug.remaining_quantity.asc())
    elif sort_by == 'stock_desc':
        query = query.order_by(Drug.remaining_quantity.desc())
    elif sort_by == 'expiry_asc':
        query = query.order_by(Drug.expiry_date.asc())
    elif sort_by == 'expiry_desc':
        query = query.order_by(Drug.expiry_date.desc())
    
    drugs = query.all()
    
    # Prepare response data
    drugs_data = []
    for drug in drugs:
        drugs_data.append({
            'id': drug.id,
            'drug_number': drug.drug_number,
            'name': drug.name,
            'specification': drug.specification,
            'expiry_date': drug.expiry_date.isoformat() if drug.expiry_date else None,
            'selling_price': float(drug.selling_price),
            'remaining_quantity': drug.remaining_quantity
        })
    
    return jsonify(drugs_data)

@app.route('/pharmacist/dosage')
@login_required
def pharmacist_dosage():
    if current_user.role != 'pharmacist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    dosages = DrugDosage.query.join(Drug).all()
    drugs = Drug.query.all()
    
    return render_template('pharmacist/dosage.html', dosages=dosages, drugs=drugs)

@app.route('/pharmacist/dosage/<int:dosage_id>')
@login_required
def pharmacist_get_dosage(dosage_id):
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    dosage = DrugDosage.query.get_or_404(dosage_id)
    
    return jsonify({
        'id': dosage.id,
        'drug': {
            'id': dosage.drug.id,
            'drug_number': dosage.drug.drug_number,
            'name': dosage.drug.name
        },
        'indication': dosage.indication,
        'contraindication': dosage.contraindication,
        'interaction': dosage.interaction,
        'side_effects': dosage.side_effects,
        'dosage_peds': dosage.dosage_peds,
        'dosage_adults': dosage.dosage_adults,
        'dosage_geriatrics': dosage.dosage_geriatrics,
        'important_notes': dosage.important_notes
    })

@app.route('/pharmacist/drugs/without-dosage')
@login_required
def pharmacist_get_drugs_without_dosage():
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    drugs = Drug.query.filter(~Drug.dosage.any()).all()
    
    return jsonify([{
        'id': drug.id,
        'drug_number': drug.drug_number,
        'name': drug.name
    } for drug in drugs])

@app.route('/pharmacist/drugs/<int:drug_id>/dosage')
@login_required
def pharmacist_get_drug_dosage(drug_id):
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    drug = Drug.query.get_or_404(drug_id)
    dosage = DrugDosage.query.filter_by(drug_id=drug.id).first()
    
    return jsonify({
        'drug': {
            'id': drug.id,
            'name': drug.name,
            'drug_number': drug.drug_number
        },
        'dosage': {
            'indication': dosage.indication if dosage else None,
            'contraindication': dosage.contraindication if dosage else None,
            'interaction': dosage.interaction if dosage else None,
            'side_effects': dosage.side_effects if dosage else None,
            'dosage_peds': dosage.dosage_peds if dosage else None,
            'dosage_adults': dosage.dosage_adults if dosage else None,
            'dosage_geriatrics': dosage.dosage_geriatrics if dosage else None,
            'important_notes': dosage.important_notes if dosage else None
        } if dosage else None
    })

@app.route('/pharmacist/inventory')
@login_required
def pharmacist_inventory():
    if current_user.role != 'pharmacist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    try:
        drugs = Drug.query.options(db.joinedload(Drug.dosage)).order_by(Drug.name).all()
        
        total_drugs = Drug.query.count()
        low_stock = Drug.query.filter(Drug.remaining_quantity < 10, Drug.remaining_quantity > 0).count()
        expiring_soon = Drug.query.filter(
            Drug.expiry_date <= date.today() + timedelta(days=30),
            Drug.expiry_date >= date.today()
        ).count()
        out_of_stock = Drug.query.filter(Drug.remaining_quantity == 0).count()
        
        return render_template('pharmacist/inventory.html',
            drugs=drugs,
            total_drugs=total_drugs,
            low_stock=low_stock,
            expiring_soon=expiring_soon,
            out_of_stock=out_of_stock
        )
        
    except Exception as e:
        current_app.logger.error(f"Error loading inventory: {str(e)}")
        flash('An error occurred while loading inventory', 'danger')
        return redirect(url_for('pharmacist_dashboard'))
    
@app.route('/pharmacist/sales')
@login_required
def pharmacist_sales():
    if current_user.role != 'pharmacist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    sales = Sale.query.order_by(Sale.created_at.desc()).limit(50).all()
    return render_template('pharmacist/sales.html', sales=sales)

@app.route('/pharmacist/drugs/export')
@login_required
def export_drugs():
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    filter_type = request.args.get('filter', 'all')
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort', 'name_asc')
    
    query = Drug.query
    
    if filter_type == 'low':
        query = query.filter(Drug.remaining_quantity < 10)
    elif filter_type == 'out':
        query = query.filter(Drug.remaining_quantity == 0)
    elif filter_type == 'expiring':
        query = query.filter(Drug.expiry_date <= date.today() + timedelta(days=30))
    
    if search_query:
        query = query.filter(
            or_(
                Drug.name.ilike(f'%{search_query}%'),
                Drug.drug_number.ilike(f'%{search_query}%'),
            )
        )
    
    if sort_by == 'name_asc':
        query = query.order_by(Drug.name.asc())
    elif sort_by == 'name_desc':
        query = query.order_by(Drug.name.desc())
    elif sort_by == 'stock_asc':
        query = query.order_by(Drug.remaining_quantity.asc())
    elif sort_by == 'stock_desc':
        query = query.order_by(Drug.remaining_quantity.desc())
    elif sort_by == 'expiry_asc':
        query = query.order_by(Drug.expiry_date.asc())
    elif sort_by == 'expiry_desc':
        query = query.order_by(Drug.expiry_date.desc())
    
    drugs = query.all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow([
        'Drug Number', 'Name', 'Expiry Date', 'Selling Price', 'Stock'
    ])
    
    for drug in drugs:
        if drug.remaining_quantity == 0:
            status = 'Out of Stock'
        elif drug.remaining_quantity < 10:
            status = 'Low Stock'
        else:
            status = 'In Stock'
        
        if drug.expiry_date and (drug.expiry_date <= date.today() + timedelta(days=30)):
            status += ' (Expiring Soon)'
        
        writer.writerow([
            drug.drug_number,
            drug.name,
            drug.expiry_date.strftime('%Y-%m-%d') if drug.expiry_date else '',
            f"Ksh {drug.selling_price:.2f}",
            drug.remaining_quantity,
        ])
    
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=drug_inventory.csv'
    response.headers['Content-type'] = 'text/csv'
    
    return response

@app.route('/pharmacist/dispense', methods=['GET', 'POST'])
@login_required
def pharmacist_dispense():
    if request.method == 'GET':
        return render_template('pharmacist/dispense.html')
    
    try:
        data = request.get_json()
        prescription_id = data.get('prescription_id')
        
        if not prescription_id:
            return jsonify({'error': 'Prescription ID is required'}), 400
        
        prescription = Prescription.query.options(
            db.joinedload(Prescription.items).joinedload(PrescriptionItem.drug)
        ).get(prescription_id)
        
        if not prescription:
            return jsonify({'error': 'Prescription not found'}), 404
        
        if prescription.status != 'pending':
            return jsonify({'error': 'Prescription has already been processed'}), 400
        
        # Verify all items are available
        for item in prescription.items:
            if item.drug.remaining_quantity < item.quantity:
                return jsonify({
                    'error': f'Insufficient stock for {item.drug.name}',
                    'details': f'Requested: {item.quantity}, Available: {item.drug.remaining_quantity}',
                    'drug_id': item.drug.id
                }), 400
        
        total_amount = sum(item.drug.selling_price * item.quantity for item in prescription.items)
        
        sale = Sale(
            sale_number=generate_sale_number(),
            prescription_id=prescription.id,
            patient_id=prescription.patient_id,
            total_amount=total_amount,
            payment_method=data.get('payment_method', 'cash'),
            pharmacist_id=current_user.id
        )
        db.session.add(sale)
        
        for item in prescription.items:
            sale_item = SaleItem(
                sale=sale,
                drug_id=item.drug_id,
                quantity=item.quantity,
                unit_price=item.drug.selling_price,
                prescription_item_id=item.id
            )
            db.session.add(sale_item)
            item.drug.remaining_quantity -= item.quantity
        
        prescription.status = 'dispensed'
        prescription.dispensed_at = datetime.utcnow()
        prescription.pharmacist_id = current_user.id
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'sale_id': sale.id,
            'sale_number': sale.sale_number,
            'total_amount': total_amount,
            'message': 'Prescription dispensed successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error dispensing prescription: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Failed to process prescription',
            'details': str(e)
        }), 500

@app.route('/pharmacist/sale', methods=['POST'])
@login_required
def process_sale():
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        if not data or 'items' not in data:
            return jsonify({'success': False, 'error': 'Invalid request data'}), 400

        items = data.get('items', [])
        payment_method = data.get('payment_method', 'cash')
        patient_id = data.get('patient_id')
        
        if not items:
            return jsonify({'success': False, 'error': 'No items in cart'}), 400

        try:
            # Generate bulk sale number if multiple items
            bulk_sale_number = None
            if len(items) > 1:
                bulk_sale_number = f"BULK-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

            total_amount = sum(float(item.get('total_price', 0)) for item in items)
            
            sale = Sale(
                sale_number=generate_sale_number(),
                bulk_sale_number=bulk_sale_number,
                patient_id=patient_id,
                user_id=current_user.id,
                pharmacist_name=f"{current_user.username} ({current_user.role})",
                total_amount=total_amount,
                payment_method=payment_method,
                status='completed',
                created_at=datetime.now()
            )
            
            db.session.add(sale)
            db.session.flush()
            
            for item in items:
                drug_id = item.get('drug_id')
                quantity = int(item.get('quantity', 1))
                unit_price = float(item.get('unit_price', 0))
                total_price = float(item.get('total_price', unit_price * quantity))
                
                if not drug_id or quantity <= 0:
                    continue
                
                drug = db.session.get(Drug, drug_id)
                if not drug:
                    db.session.rollback()
                    return jsonify({
                        'success': False,
                        'error': f'Drug with ID {drug_id} not found'
                    }), 400
                
                if drug.remaining_quantity < quantity:
                    db.session.rollback()
                    return jsonify({
                        'success': False,
                        'error': f'Insufficient stock for {drug.name}',
                        'available': drug.remaining_quantity,
                        'requested': quantity,
                        'drug_id': drug.id
                    }), 400
                
                sale_item = SaleItem(
                    sale_id=sale.id,
                    drug_id=drug_id,
                    drug_name=drug.name,
                    drug_specification=drug.specification,
                    individual_sale_number=generate_sale_number(),
                    description=f"Sale of {drug.name}",
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=total_price,
                    created_at=datetime.now()
                )
                
                db.session.add(sale_item)
                drug.sold_quantity += quantity
                db.session.add(drug)
            
            transaction = Transaction(
                transaction_number=generate_transaction_number(),
                transaction_type='sale',
                amount=total_amount,
                user_id=current_user.id,
                reference_id=sale.id,
                notes=f"Sale #{sale.sale_number}",
                created_at=datetime.now()
            )
            db.session.add(transaction)
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'sale_id': sale.id,
                'sale_number': sale.sale_number,
                'bulk_sale_number': sale.bulk_sale_number,
                'total_amount': sale.total_amount,
                'message': 'Sale processed successfully'
            })
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error processing sale items: {str(e)}", exc_info=True)
            raise e
            
    except Exception as e:
        current_app.logger.error(f"Error processing sale: {str(e)}", exc_info=True)
        return jsonify({
            'success': False, 
            'error': 'Failed to process sale',
            'details': str(e)
        }), 500

@app.route('/pharmacist/sale/<int:sale_id>/receipt')
@login_required
def generate_receipt(sale_id):
    if current_user.role != 'pharmacist':
        abort(403)
    
    sale = db.session.query(Sale).options(
        db.joinedload(Sale.user),
        db.joinedload(Sale.items).joinedload(SaleItem.drug),
        db.joinedload(Sale.patient)
    ).where(Sale.id == sale_id).first()
    
    if not sale:
        abort(404)
    
    related_sales = []
    if sale.bulk_sale_number:
        related_sales = db.session.query(Sale).filter(
            Sale.bulk_sale_number == sale.bulk_sale_number,
            Sale.id != sale.id
        ).options(
            db.joinedload(Sale.items).joinedload(SaleItem.drug)
        ).all()
    
    return render_template('pharmacist/receipt.html', 
                         sale=sale,
                         related_sales=related_sales,
                         now=datetime.now())

@app.route('/pharmacist/refunds')
@login_required
def pharmacist_refunds():
    if current_user.role != 'pharmacist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    return render_template('pharmacist/refunds.html')

@app.route('/pharmacist/sales/search', methods=['GET'])
@login_required
def search_sale():
    sale_number = request.args.get('sale_number')
    
    sale = Sale.query.filter((Sale.sale_number == sale_number) | 
                           (Sale.bulk_sale_number == sale_number)).first()
    
    if not sale:
        return jsonify({'error': 'Sale not found'}), 404
    
    items = []
    for item in sale.items:
        items.append({
            'id': item.id,
            'individual_sale_number': item.individual_sale_number,
            'drug_id': item.drug_id,
            'drug_name': item.drug.name,
            'quantity_sold': item.quantity,
            'quantity_remaining': item.quantity - sum(
                ri.quantity for ri in item.refunds
            ) if item.refunds else item.quantity,
            'unit_price': item.unit_price,
            'total_price': item.total_price
        })
    
    return jsonify({
        'sale_number': sale.sale_number,
        'bulk_sale_number': sale.bulk_sale_number,
        'is_bulk': bool(sale.bulk_sale_number),
        'created_at': sale.created_at.strftime('%Y-%m-%d %H:%M'),
        'patient_name': sale.patient.name if sale.patient else 'Walk-in',
        'total_amount': sale.total_amount,
        'items': items
    })

@app.route('/pharmacist/refund/search', methods=['GET'])
@login_required
def search_sale_for_refund():
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    sale_number = request.args.get('sale_number')
    if not sale_number:
        return jsonify({'error': 'Sale number is required'}), 400
    
    sale = db.session.query(Sale).filter(
        (Sale.sale_number == sale_number) | 
        (Sale.bulk_sale_number == sale_number)
    ).first()
    
    if not sale:
        return jsonify({'error': 'Sale not found'}), 404
    
    items = []
    for item in sale.items:
        if item.drug_id:
            refunded_qty = sum(ri.quantity for ri in item.refund_items) if item.refund_items else 0
            remaining_qty = item.quantity - refunded_qty
            
            if remaining_qty > 0:
                items.append({
                    'id': item.id,
                    'sale_item_id': item.id,
                    'drug_id': item.drug_id,
                    'drug_name': item.drug_name,
                    'unit_price': item.unit_price,
                    'quantity_sold': item.quantity,
                    'quantity_refunded': refunded_qty,
                    'quantity_remaining': remaining_qty,
                    'total_price': item.total_price
                })
    
    return jsonify({
        'sale_id': sale.id,
        'sale_number': sale.sale_number,
        'bulk_sale_number': sale.bulk_sale_number,
        'is_bulk': bool(sale.bulk_sale_number),
        'created_at': sale.created_at.strftime('%Y-%m-%d %H:%M'),
        'patient_name': sale.patient.decrypted_name if sale.patient else 'Walk-in Customer',
        'total_amount': sale.total_amount,
        'items': items
    })

@app.route('/pharmacist/refund', methods=['POST'])
@login_required
def process_refund():
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    sale_id = data.get('sale_id')
    items = data.get('items', [])
    reason = data.get('reason', '')
    
    if not sale_id:
        return jsonify({'error': 'Sale ID is required'}), 400
    
    if not items:
        return jsonify({'error': 'No items selected for refund'}), 400
    
    sale = db.session.get(Sale, sale_id)
    if not sale:
        return jsonify({'error': 'Sale not found'}), 404
    
    try:
        refund = Refund(
            refund_number=generate_refund_number(),
            sale_id=sale.id,
            user_id=current_user.id,
            total_amount=0,
            status='completed',
            reason=reason
        )
        db.session.add(refund)
        db.session.flush()
        
        total_amount = 0
        
        for item_data in items:
            sale_item_id = item_data.get('sale_item_id')
            quantity = int(item_data.get('quantity'))
            
            if quantity <= 0:
                continue
            
            sale_item = db.session.get(SaleItem, sale_item_id)
            if not sale_item or sale_item.sale_id != sale.id:
                continue
            
            refunded_qty = sum(ri.quantity for ri in sale_item.refund_items) if sale_item.refund_items else 0
            max_refundable = sale_item.quantity - refunded_qty
            
            if quantity > max_refundable:
                return jsonify({
                    'error': f'Cannot refund more than {max_refundable} for {sale_item.drug_name}'
                }), 400
            
            if sale_item.drug_id:
                drug = db.session.get(Drug, sale_item.drug_id)
                if drug:
                    drug.sold_quantity -= quantity
                    drug.stocked_quantity += quantity
            
            item_total = sale_item.unit_price * quantity
            refund_item = RefundItem(
                refund_id=refund.id,
                sale_item_id=sale_item.id,
                quantity=quantity,
                unit_price=sale_item.unit_price,
                total_price=item_total
            )
            db.session.add(refund_item)
            
            total_amount += item_total
        
        refund.total_amount = total_amount
        
        transaction = Transaction(
            transaction_number=generate_transaction_number(),
            transaction_type='refund',
            amount=total_amount,
            user_id=current_user.id,
            reference_id=refund.id,
            notes=f'Refund for sale {sale.sale_number}'
        )
        db.session.add(transaction)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'refund_id': refund.id,
            'refund_number': refund.refund_number,
            'total_amount': total_amount
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

def generate_refund_number():
    return f"REF-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

@app.route('/pharmacist/refund/<int:refund_id>/receipt')
@login_required
def refund_receipt(refund_id):
    if current_user.role != 'pharmacist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    refund = db.session.query(Refund).options(
        db.joinedload(Refund.sale).joinedload(Sale.patient),
        db.joinedload(Refund.user),
        db.joinedload(Refund.items).joinedload(RefundItem.sale_item)
    ).get(refund_id)
    
    if not refund:
        flash('Refund not found', 'danger')
        return redirect(url_for('pharmacist_refunds'))
    
    return render_template('pharmacist/refund_receipt.html', refund=refund)



@app.route('/pharmacist/prescription/<int:prescription_id>')
@login_required
def get_prescription_details(prescription_id):
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        prescription = Prescription.query.options(
            db.joinedload(Prescription.items).joinedload(PrescriptionItem.drug)
        ).get(prescription_id)
        
        if not prescription:
            return jsonify({'error': 'Prescription not found'}), 404
        
        items_data = []
        for item in prescription.items:
            items_data.append({
                'id': item.id,
                'drug_id': item.drug_id,
                'drug_name': item.drug.name,
                'quantity': item.quantity,
                'drug': {
                    'id': item.drug.id,
                    'name': item.drug.name,
                    'selling_price': float(item.drug.selling_price),
                    'remaining_quantity': item.drug.remaining_quantity
                }
            })
        
        return jsonify({
            'id': prescription.id,
            'patient_id': prescription.patient_id,
            'patient_name': prescription.patient.decrypted_name,
            'doctor_name': prescription.doctor.decrypted_name,
            'created_at': prescription.created_at.strftime('%Y-%m-%d %H:%M'),
            'items': items_data,
            'items_count': len(items_data)
        })
    
    except Exception as e:
        current_app.logger.error(f"Error fetching prescription details: {str(e)}")
        return jsonify({'error': 'Failed to fetch prescription details'}), 500

@app.route('/pharmacist/dispense', methods=['POST'])
@login_required
def dispense_prescription():
    if current_user.role != 'pharmacist':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        prescription_id = data.get('prescription_id')
        
        if not prescription_id:
            return jsonify({'error': 'Prescription ID is required'}), 400
        
        prescription = Prescription.query.options(
            db.joinedload(Prescription.items).joinedload(PrescriptionItem.drug),
            db.joinedload(Prescription.patient),
            db.joinedload(Prescription.doctor)
        ).get(prescription_id)
        
        if not prescription:
            return jsonify({'error': 'Prescription not found'}), 404
        
        if prescription.status != 'pending':
            return jsonify({'error': 'Prescription has already been processed'}), 400
        
        for item in prescription.items:
            if item.drug.remaining_quantity < item.quantity:
                return jsonify({
                    'error': f'Insufficient stock for {item.drug.name}',
                    'details': f'Requested: {item.quantity}, Available: {item.drug.remaining_quantity}',
                    'drug_id': item.drug.id
                }), 400
        
        total_amount = sum(item.drug.selling_price * item.quantity for item in prescription.items)
        
        sale = Sale(
            sale_number=generate_sale_number(),
            prescription_id=prescription.id,
            patient_id=prescription.patient_id,
            total_amount=total_amount,
            payment_method=data.get('payment_method', 'cash'),
            pharmacist_id=current_user.id
        )
        db.session.add(sale)
        
        for item in prescription.items:
            sale_item = SaleItem(
                sale=sale,
                drug_id=item.drug_id,
                quantity=item.quantity,
                unit_price=item.drug.selling_price,
                prescription_item_id=item.id
            )
            db.session.add(sale_item)
            item.drug.remaining_quantity -= item.quantity
        
        prescription.status = 'dispensed'
        prescription.dispensed_at = datetime.utcnow()
        prescription.pharmacist_id = current_user.id
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'sale_id': sale.id,
            'sale_number': sale.sale_number,
            'total_amount': total_amount,
            'message': 'Prescription dispensed successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error dispensing prescription: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Failed to process prescription',
            'details': str(e)
        }), 500
    
    
@app.route('/pharmacist/prescriptions')
@login_required
def pharmacist_prescriptions():
    if current_user.role != 'pharmacist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    # Get all completed prescriptions that haven't been dispensed yet
    prescriptions = Prescription.query.filter(
        Prescription.status == 'completed',
    ).order_by(Prescription.created_at.asc()).all()
    
    return render_template('pharmacist/prescriptions.html',
        prescriptions=prescriptions
    )
        
# Doctor Routes
@app.route('/doctor')
@login_required
def doctor_dashboard():
    if current_user.role != 'doctor':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    # Get counts for the stats cards
    active_patients_count = Patient.query.filter_by(status='active').count()
    today_patients = Patient.query.filter(
        func.date(Patient.created_at) == date.today()
    ).count()
    completed_patients_count = Patient.query.filter_by(status='completed').count()
    
    # Get actual patient lists for the tables
    active_patients = Patient.query.filter_by(status='active').order_by(Patient.updated_at.desc()).limit(50).all()
    completed_patients = Patient.query.filter_by(status='completed').order_by(Patient.updated_at.desc()).limit(50).all()
    
    return render_template('doctor/dashboard.html',
        active_patients_count=active_patients_count,
        today_patients=today_patients,
        completed_patients_count=completed_patients_count,
        active_patients=active_patients,
        completed_patients=completed_patients,
        recent_activities=[]  # Empty list until audit is properly set up
    )

        
@app.route('/generate_patient_number')
@login_required
def get_patient_number():
    patient_type = request.args.get('type')
    if patient_type not in ['OP', 'IP']:
        return jsonify({'error': 'Invalid patient type'}), 400
    
    number = generate_patient_number(patient_type)
    return jsonify({'number': number})

def generate_patient_number(patient_type):
    """Generate patient number in format OP MNC001 or IP MNC001"""
    prefix = 'OP' if patient_type == 'OP' else 'IP'
    last_patient = Patient.query.filter(
        Patient.op_number.like(f'{prefix} MNC%') if patient_type == 'OP' else Patient.ip_number.like(f'{prefix} MNC%')
    ).order_by(
        Patient.op_number.desc() if patient_type == 'OP' else Patient.ip_number.desc()
    ).first()
    
    if last_patient:
        last_number_str = (last_patient.op_number if patient_type == 'OP' else last_patient.ip_number).split('MNC')[-1]
        last_number = int(last_number_str)
        new_number = f"{prefix} MNC{str(last_number + 1).zfill(3)}"
    else:
        new_number = f"{prefix} MNC001"
    
    return new_number

@app.route('/doctor/patients', methods=['GET'])
@login_required
def doctor_patients():
    if current_user.role != 'doctor':
        flash('Unauthorized', 'danger')
        return redirect(url_for('home'))

    active_patients = Patient.query.filter_by(status='active').order_by(Patient.created_at.desc()).all()
    completed_patients = Patient.query.filter_by(status='completed').order_by(Patient.updated_at.desc()).all()

    return render_template(
        'doctor/patients.html',
        active_patients=active_patients,
        completed_patients=completed_patients
    )


# Doctor Routes - Complete with all sections
@app.route('/doctor/patient/new', methods=['GET', 'POST'])
@login_required
def doctor_new_patient():
    if current_user.role != 'doctor':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        section = request.form.get('section')
        patient_id = request.form.get('patient_id')
        try:
            if section == 'biodata':
                patient_type = request.form.get('patient_type')
                patient_number = generate_patient_number(patient_type)
                
                patient = Patient(
                    op_number=patient_number if patient_type == 'OP' else None,
                    ip_number=patient_number if patient_type == 'IP' else None,
                    name=Config.encrypt_data_static(request.form.get('name')),
                    age=int(request.form.get('age')) if request.form.get('age') else None,
                    gender=request.form.get('gender'),
                    address=Config.encrypt_data_static(request.form.get('address')) if request.form.get('address') else None,
                    phone=Config.encrypt_data_static(request.form.get('phone')) if request.form.get('phone') else None,
                    destination=request.form.get('destination'),
                    occupation=Config.encrypt_data_static(request.form.get('occupation')) if request.form.get('occupation') else None,
                    religion=request.form.get('religion'),
                    nok_name=Config.encrypt_data_static(request.form.get('nok_name')) if request.form.get('nok_name') else None,
                    nok_contact=Config.encrypt_data_static(request.form.get('nok_contact')) if request.form.get('nok_contact') else None,
                    tca=datetime.strptime(request.form.get('tca'), '%Y-%m-%d').date() if request.form.get('tca') else None,
                    date_of_admission=datetime.strptime(request.form.get('date_of_admission'), '%Y-%m-%d').date() if request.form.get('date_of_admission') else date.today(),
                    status='active'
                )
                db.session.add(patient)
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'patient_id': patient.id,
                    'next_section': 'chief_complaint'
                })

            elif section == 'chief_complaint':
                patient = db.session.get(Patient, patient_id)
                if not patient:
                    return jsonify({'success': False, 'error': 'Patient not found'})
                
                patient.chief_complaint = request.form.get('chief_complaint')
                patient.history_present_illness = request.form.get('history_present_illness')
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'next_section': 'review_systems'
                })
                
            elif section == 'review_systems':
                patient = Patient.query.get(patient_id)
                if not patient:
                    return jsonify({'success': False, 'error': 'Patient not found'})
                
                review = PatientReviewSystem.query.filter_by(patient_id=patient.id).first()
                if not review:
                    review = PatientReviewSystem(patient_id=patient.id)
                    db.session.add(review)
                
                review.cns = request.form.get('cns')
                review.cvs = request.form.get('cvs')
                review.rs = request.form.get('rs')
                review.git = request.form.get('git')
                review.gut = request.form.get('gut')
                review.skin = request.form.get('skin')
                review.msk = request.form.get('msk')
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'next_section': 'hpi'
                })

            elif section == 'hpi':
                patient = Patient.query.get(patient_id)
                if not patient:
                    return jsonify({'success': False, 'error': 'Patient not found'})
                
                patient.history_present_illness = request.form.get('hpi_details')
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'next_section': 'smhx'
                })

            elif section == 'smhx':
                patient = Patient.query.get(patient_id)
                if not patient:
                    return jsonify({'success': False, 'error': 'Patient not found'})
                
                smhx = PatientHistory.query.filter_by(patient_id=patient.id).first()
                if not smhx:
                    smhx = PatientHistory(patient_id=patient.id)
                    db.session.add(smhx)
                
                smhx.social_history = request.form.get('social_history')
                smhx.medical_history = request.form.get('medical_history')
                smhx.surgical_history = request.form.get('surgical_history')
                smhx.family_history = request.form.get('family_history')
                smhx.allergies = request.form.get('allergies')
                smhx.medications = request.form.get('medications')
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'next_section': 'examination'
                })

            elif section == 'examination':
                patient = Patient.query.get(patient_id)
                if not patient:
                    return jsonify({'success': False, 'error': 'Patient not found'})
                
                exam = PatientExamination.query.filter_by(patient_id=patient.id).first()
                if not exam:
                    exam = PatientExamination(patient_id=patient.id)
                    db.session.add(exam)
                
                exam.general_appearance = request.form.get('general_appearance')
                exam.jaundice = request.form.get('jaundice') == 'yes'
                exam.pallor = request.form.get('pallor') == 'yes'
                exam.cyanosis = request.form.get('cyanosis') == 'yes'
                exam.lymphadenopathy = request.form.get('lymphadenopathy') == 'yes'
                exam.edema = request.form.get('edema') == 'yes'
                exam.dehydration = request.form.get('dehydration') == 'yes'
                exam.dehydration_parameters = request.form.get('dehydration_parameters')
                exam.temperature = float(request.form.get('temperature')) if request.form.get('temperature') else None
                exam.pulse = int(request.form.get('pulse')) if request.form.get('pulse') else None
                exam.resp_rate = int(request.form.get('resp_rate')) if request.form.get('resp_rate') else None
                exam.bp_systolic = int(request.form.get('bp_systolic')) if request.form.get('bp_systolic') else None
                exam.bp_diastolic = int(request.form.get('bp_diastolic')) if request.form.get('bp_diastolic') else None
                exam.spo2 = int(request.form.get('spo2')) if request.form.get('spo2') else None
                exam.weight = float(request.form.get('weight')) if request.form.get('weight') else None
                exam.height = float(request.form.get('height')) if request.form.get('height') else None
                exam.bmi = float(request.form.get('bmi')) if request.form.get('bmi') else None
                exam.cvs_exam = request.form.get('cvs_exam')
                exam.resp_exam = request.form.get('resp_exam')
                exam.abdo_exam = request.form.get('abdo_exam')
                exam.cns_exam = request.form.get('cns_exam')
                exam.msk_exam = request.form.get('msk_exam')
                exam.skin_exam = request.form.get('skin_exam')
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'next_section': 'diagnosis'
                })

            elif section == 'diagnosis':
                patient = Patient.query.get(patient_id)
                if not patient:
                    return jsonify({'success': False, 'error': 'Patient not found'})
                
                diagnosis = PatientDiagnosis.query.filter_by(patient_id=patient.id).first()
                if not diagnosis:
                    diagnosis = PatientDiagnosis(patient_id=patient.id)
                    db.session.add(diagnosis)
                
                diagnosis.working_diagnosis = request.form.get('working_diagnosis')
                diagnosis.differential_diagnosis = request.form.get('differential_diagnosis')
                
                # Lab requests
                if request.form.getlist('lab_tests'):
                    for test_id in request.form.getlist('lab_tests'):
                        lab_request = LabRequest(
                            patient_id=patient.id,
                            test_id=test_id,
                            requested_by=current_user.id,
                            status='pending',
                            notes=request.form.get('lab_notes')
                        )
                        db.session.add(lab_request)
                
                # Imaging requests
                if request.form.getlist('imaging_tests'):
                    for test_id in request.form.getlist('imaging_tests'):
                        imaging_request = ImagingRequest(
                            patient_id=patient.id,
                            test_id=test_id,
                            requested_by=current_user.id,
                            status='pending',
                            notes=request.form.get('imaging_notes')
                        )
                        db.session.add(imaging_request)
                
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'next_section': 'management'
                })

            elif section == 'management':
                patient = Patient.query.get(patient_id)
                if not patient:
                    return jsonify({'success': False, 'error': 'Patient not found'})
                
                management = PatientManagement.query.filter_by(patient_id=patient.id).first()
                if not management:
                    management = PatientManagement(patient_id=patient.id)
                    db.session.add(management)
                
                management.treatment_plan = request.form.get('treatment_plan')
                management.follow_up = request.form.get('follow_up')
                management.notes = request.form.get('management_notes')
                
                # Prescriptions
                if request.form.getlist('drug_id'):
                    for i, drug_id in enumerate(request.form.getlist('drug_id')):
                        prescription = Prescription(
                            patient_id=patient.id,
                            drug_id=drug_id,
                            doctor_id=current_user.id,
                            dosage=request.form.getlist('dosage')[i],
                            frequency=request.form.getlist('frequency')[i],
                            duration=request.form.getlist('duration')[i],
                            quantity=request.form.getlist('quantity')[i],
                            notes=request.form.getlist('prescription_notes')[i]
                        )
                        db.session.add(prescription)
                
                # Services
                if request.form.getlist('service_id'):
                    for service_id in request.form.getlist('service_id'):
                        service_record = PatientService(
                            patient_id=patient.id,
                            service_id=service_id,
                            performed_by=current_user.id,
                            notes=request.form.get('service_notes')
                        )
                        db.session.add(service_record)
                
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'redirect': url_for('doctor_patient_details', patient_id=patient.id)
                })

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Patient form error: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            })

    # For GET request - render the form
    lab_tests = LabTest.query.all()
    imaging_tests = ImagingTest.query.all()
    drugs = Drug.query.filter(Drug.remaining_quantity > 0).all()
    services = Service.query.all()
    
    return render_template('doctor/new_patient.html',
        lab_tests=lab_tests,
        imaging_tests=imaging_tests,
        drugs=drugs,
        services=services,
        current_date=date.today().strftime('%Y-%m-%d')
    )


from openai import OpenAI
from flask import jsonify, request, current_app
from functools import wraps
import time

# In your configuration/initialization code
deepseek_client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1",  # Note the /v1 suffix
    timeout=30.0
)

# Optional OpenAI fallback
if os.getenv("OPENAI_API_KEY"):
    openai.api_key = os.getenv("OPENAI_API_KEY")
    
@app.route('/api/verify-models', methods=['GET'])
@login_required
def verify_models():
    """Endpoint to check available models"""
    try:
        # Test DeepSeek
        deepseek_models = deepseek_client.models.list()
        current_app.logger.info(f"DeepSeek available models: {[m.id for m in deepseek_models.data]}")
        
        # Test OpenAI if configured
        openai_models = []
        if 'openai' in globals():
            openai_models = openai.Model.list()
        
        return jsonify({
            'deepseek_models': [m.id for m in deepseek_models.data],
            'openai_models': [m.id for m in openai_models.data] if openai_models else []
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/doctor/patient/ai/review_systems', methods=['POST'])
@login_required
def ai_review_systems():
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    patient_id = request.form.get('patient_id')
    if not patient_id:
        return jsonify({'success': False, 'error': 'Patient ID required'}), 400
    
    patient = db.session.get(Patient, patient_id)
    if not patient:
        return jsonify({'success': False, 'error': 'Patient not found'}), 404
    
    try:
        patient_data = {
            'age': patient.age,
            'gender': patient.gender,
            'address': patient.decrypted_address or '',
            'chief_complaint': patient.chief_complaint or '',
            'occupation': patient.decrypted_occupation or '',
            'religion': patient.religion or '',
        }
        
        questions = AIService.generate_review_systems_questions(patient_data)
        if not questions:
            return jsonify({
                'success': False,
                'error': 'Failed to generate questions'
            }), 500
            
        # Save to review systems record
        review = PatientReviewSystem.query.filter_by(patient_id=patient.id).first()
        if not review:
            review = PatientReviewSystem(patient_id=patient.id)
            db.session.add(review)
        
        review.ai_suggested_questions = questions
        review.ai_last_updated = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'questions': questions
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Review systems AI error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'details': str(e)
        }), 500
@app.route('/doctor/patient/ai/hpi_questions', methods=['POST'])
@login_required
def ai_hpi_questions():
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    patient_id = request.form.get('patient_id')
    if not patient_id:
        return jsonify({'success': False, 'error': 'Patient ID required'}), 400
    
    # Updated to use SQLAlchemy 2.0 style query
    patient = db.session.get(Patient, patient_id)
    if not patient:
        return jsonify({'success': False, 'error': 'Patient not found'}), 404
    
    try:
        patient_data = {
            'age': patient.age,
            'gender': patient.gender,
            'address': patient.decrypted_address or '',
            'chief_complaint': patient.chief_complaint or '',
            'occupation': patient.decrypted_occupation or '',
            'religion': patient.religion or '',
        }
        
        questions = AIService.generate_hpi_questions(patient_data)
        if not questions:
            return jsonify({
                'success': False,
                'error': 'Failed to generate questions'
            }), 500
            
        return jsonify({
            'success': True,
            'questions': questions
        })
        
    except Exception as e:
        current_app.logger.error(f"HPI questions AI error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route('/doctor/patient/ai/generate_hpi', methods=['POST'])
@login_required
def ai_generate_hpi():
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    patient_id = request.form.get('patient_id')
    if not patient_id:
        return jsonify({'success': False, 'error': 'Patient ID required'}), 400
    
    # Updated to SQLAlchemy 2.0 style query
    patient = db.session.get(Patient, patient_id)
    if not patient:
        return jsonify({'success': False, 'error': 'Patient not found'}), 404
    
    try:
        # Get patient history if exists
        history = db.session.scalar(
            db.select(PatientHistory)
            .filter_by(patient_id=patient.id)
            .limit(1)
        )
        
        # Get review systems if exists
        review = db.session.scalar(
            db.select(PatientReviewSystem)
            .filter_by(patient_id=patient.id)
            .limit(1)
        )
        
        # Build patient data safely
        patient_data = {
            'age': patient.age,
            'gender': patient.gender,
            'address': patient.decrypted_address or '',
            'chief_complaint': patient.chief_complaint or '',
            'occupation': patient.decrypted_occupation or '',
            'religion': patient.religion or '',
            'review_systems': (
                f"CNS: {review.cns or 'Not documented'}\n"
                f"CVS: {review.cvs or 'Not documented'}\n"
                f"GIT: {review.git or 'Not documented'}\n"
                f"GUT: {review.gut or 'Not documented'}\n"
                f"Skin: {review.skin or 'Not documented'}\n"
                f"MSK: {review.msk or 'Not documented'}\n"
                f"RS: {review.rs or 'Not documented'}"
            ) if review else 'Review of systems not documented'
        }
        
        hpi_content = AIService.generate_hpi_content(patient_data)
        if not hpi_content:
            return jsonify({
                'success': False,
                'error': 'Failed to generate HPI content'
            }), 500
            
        return jsonify({
            'success': True,
            'hpi_content': hpi_content
        })
        
    except Exception as e:
        current_app.logger.error(f"HPI generation AI error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500
        
@app.route('/doctor/patient/ai/diagnosis', methods=['POST'])
@login_required
def ai_diagnosis():
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        patient_id = request.form.get('patient_id')
        if not patient_id:
            return jsonify({'success': False, 'error': 'Patient ID required'}), 400
        
        patient = db.session.get(Patient, patient_id)
        if not patient:
            return jsonify({'success': False, 'error': 'Patient not found'}), 404
        
        # Get related records safely
        review_systems = db.session.scalar(
            db.select(PatientReviewSystem)
            .filter_by(patient_id=patient.id)
            .limit(1)
        )
        
        history = db.session.scalar(
            db.select(PatientHistory)
            .filter_by(patient_id=patient.id)
            .limit(1)
        )
        
        examination = db.session.scalar(
            db.select(PatientExamination)
            .filter_by(patient_id=patient.id)
            .limit(1)
        )

        patient_data = {
            'age': patient.age,
            'gender': patient.gender,
            'address': patient.decrypted_address or '',
            'occupation': patient.decrypted_occupation or '',
            'religion': patient.religion or '',
            'chief_complaint': patient.chief_complaint or '',
            'history_present_illness': patient.history_present_illness or '',
            'review_systems': {
                'cns': review_systems.cns if review_systems else '',
                'cvs': review_systems.cvs if review_systems else '',
                'git': review_systems.git if review_systems else '',
                'gut': review_systems.gut if review_systems else '',
                'skin': review_systems.skin if review_systems else '',
                'msk': review_systems.msk if review_systems else '',
                'rs': review_systems.rs if review_systems else ''
            },
            'social_history': history.social_history if history else '',
            'medical_history': history.medical_history if history else '',
            'surgical_history': history.surgical_history if history else '',
            'family_history': history.family_history if history else '',
            'allergies': history.allergies if history else '',
            'medications': history.medications if history else '',
            'examination': {
                'general_appearance': examination.general_appearance if examination else '',
                'vitals': {
                    'temperature': examination.temperature if examination else None,
                    'pulse': examination.pulse if examination else None,
                    'resp_rate': examination.resp_rate if examination else None,
                    'bp': f"{examination.bp_systolic}/{examination.bp_diastolic}" if examination else None,
                    'spo2': examination.spo2 if examination else None,
                    'weight': examination.weight if examination else None,
                    'height': examination.height if examination else None,
                    'bmi': examination.bmi if examination else None
                },
                'systems': {
                    'cvs': examination.cvs_exam if examination else '',
                    'respiratory': examination.resp_exam if examination else '',
                    'abdominal': examination.abdo_exam if examination else '',
                    'cns': examination.cns_exam if examination else '',
                    'msk': examination.msk_exam if examination else '',
                    'skin': examination.skin_exam if examination else ''
                }
            }
        }
        
        diagnosis = AIService.generate_diagnosis(patient_data)
        if not diagnosis:
            return jsonify({
                'success': False,
                'error': 'AI service unavailable. Please try again later.'
            }), 503
            
        return jsonify({
            'success': True,
            'diagnosis': diagnosis
        })
        
    except Exception as e:
        current_app.logger.error(f"Diagnosis route error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500
        
@app.route('/doctor/patient/ai/analyze_lab', methods=['POST'])
@login_required
def ai_analyze_lab():
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    patient_id = request.form.get('patient_id')
    lab_text = request.form.get('lab_text')
    
    if not patient_id or not lab_text:
        return jsonify({'success': False, 'error': 'Patient ID and lab text required'}), 400
    
    patient = db.session.get(Patient, patient_id)
    if not patient:
        return jsonify({'success': False, 'error': 'Patient not found'}), 404
    
    try:
        diagnosis = PatientDiagnosis.query.filter_by(patient_id=patient.id).first()
        
        patient_data = {
            'age': patient.age,
            'gender': patient.gender,
            'chief_complaint': patient.chief_complaint or '',
            'diagnosis': diagnosis.working_diagnosis if diagnosis else ''
        }
        
        analysis = AIService.analyze_lab_results(patient_data, lab_text)
        if not analysis:
            return jsonify({
                'success': False,
                'error': 'Failed to analyze lab results'
            }), 500
            
        return jsonify({
            'success': True,
            'analysis': analysis
        })
        
    except Exception as e:
        current_app.logger.error(f"Lab analysis AI error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@app.route('/doctor/patient/ai/treatment', methods=['POST'])
@login_required
def ai_treatment():
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    patient_id = request.form.get('patient_id')
    if not patient_id:
        return jsonify({'success': False, 'error': 'Patient ID required'}), 400
    
    patient = db.session.get(Patient, patient_id)
    if not patient:
        return jsonify({'success': False, 'error': 'Patient not found'}), 404
    
    try:
        diagnosis = PatientDiagnosis.query.filter_by(patient_id=patient.id).first()
        history = PatientHistory.query.filter_by(patient_id=patient.id).first()
        
        if not diagnosis or not diagnosis.working_diagnosis:
            return jsonify({'success': False, 'error': 'Diagnosis required'}), 400
        
        available_drugs = Drug.query.filter(Drug.remaining_quantity > 0).all()
        
        patient_data = {
            'age': patient.age,
            'gender': patient.gender,
            'diagnosis': diagnosis.working_diagnosis,
            'allergies': history.allergies if history else 'None known',
            'medications': history.medications if history else 'None'
        }
        
        treatment_plan = AIService.generate_treatment_plan(patient_data, available_drugs)
        if not treatment_plan:
            return jsonify({
                'success': False,
                'error': 'Failed to generate treatment plan'
            }), 500
            
        # Save to management record
        management = PatientManagement.query.filter_by(patient_id=patient.id).first()
        if not management:
            management = PatientManagement(patient_id=patient.id)
            db.session.add(management)
        
        management.ai_generated_plan = True
        management.ai_alternative_treatments = treatment_plan
        management.ai_last_updated = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'treatment_plan': treatment_plan
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Treatment plan AI error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'details': str(e)
        }), 500
 
@app.errorhandler(APITimeoutError)
def handle_ai_timeout(e):
    return jsonify({
        "error": "AI service timeout",
        "message": "The AI service is taking longer than expected to respond"
    }), 504

@app.errorhandler(APIError)
def handle_ai_error(e):
    return jsonify({
        "error": "AI service error",
        "message": str(e)
    }), 502
        
@app.route('/doctor/patients/active')
@login_required
def active_patients():
    if current_user.role != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403
    
    patients = Patient.query.filter_by(status='active').order_by(Patient.created_at.desc()).all()
    patients_data = [{
        'id': p.id,
        'number': p.op_number or p.ip_number,
        'name': p.name,
        'age': p.age,
        'gender': p.gender,
        'date_of_admission': p.date_of_admission.strftime('%Y-%m-%d')
    } for p in patients]
    
    return jsonify(patients_data)

@app.route('/doctor/patients/old', methods=['GET', 'POST'])
@login_required
def old_patients():
    if current_user.role != 'doctor':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))

    # Handle search and filtering
    search_query = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20  # Patients per page

    # Base query for completed patients
    query = Patient.query.filter_by(status='completed')

    # Apply search filter if provided
    if search_query:
        query = query.filter(
            or_(
                Patient.name.ilike(f'%{search_query}%'),
                Patient.op_number.ilike(f'%{search_query}%'),
                Patient.ip_number.ilike(f'%{search_query}%')
            )
        )

    # Get paginated results ordered by completion date (newest first)
    completed_patients = query.order_by(
        Patient.updated_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'readmit':
            patient_id = request.form.get('patient_id')
            patient = Patient.query.get(patient_id)
            if patient:
                try:
                    patient.status = 'active'
                    patient.updated_at = datetime.utcnow()
                    db.session.commit()
                    
                    log_audit('readmit_patient', 'Patient', patient.id, None, None)
                    flash(f'Patient {patient.name} readmitted successfully!', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error readmitting patient: {str(e)}', 'danger')
            else:
                flash('Patient not found', 'danger')
        
        return redirect(url_for('old_patients'))

    return render_template('doctor/old_patients.html',
        patients=completed_patients,
        search_query=search_query,
        current_time=datetime.utcnow()
    )

@app.route('/doctor/patient/<int:patient_id>/record')
@login_required
def patient_medical_record(patient_id):
    if current_user.role != 'doctor':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))

    patient = Patient.query.get_or_404(patient_id)
    
    # Get all medical record components
    review_systems = PatientReviewSystem.query.filter_by(patient_id=patient.id).first()
    history = PatientHistory.query.filter_by(patient_id=patient.id).first()
    examination = PatientExamination.query.filter_by(patient_id=patient.id).first()
    diagnosis = PatientDiagnosis.query.filter_by(patient_id=patient.id).first()
    management = PatientManagement.query.filter_by(patient_id=patient.id).first()
    
    # Get all related records
    lab_requests = LabRequest.query.filter_by(patient_id=patient.id).order_by(LabRequest.created_at.desc()).all()
    imaging_requests = ImagingRequest.query.filter_by(patient_id=patient.id).order_by(ImagingRequest.created_at.desc()).all()
    prescriptions = Prescription.query.filter_by(patient_id=patient.id).order_by(Prescription.created_at.desc()).all()
    services = PatientService.query.filter_by(patient_id=patient.id).order_by(PatientService.created_at.desc()).all()
    
    return render_template('doctor/medical_record.html',
        patient=patient,
        review_systems=review_systems,
        history=history,
        examination=examination,
        diagnosis=diagnosis,
        management=management,
        lab_requests=lab_requests,
        imaging_requests=imaging_requests,
        prescriptions=prescriptions,
        services=services
    )

@app.route('/doctor/patient/<int:patient_id>/complete', methods=['POST'])
@login_required
def complete_patient_treatment(patient_id):
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    patient = Patient.query.get_or_404(patient_id)
    try:
        patient.status = 'completed'
        patient.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/doctor/patient/<int:patient_id>', methods=['DELETE'])
@login_required
def delete_patient(patient_id):
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    patient = Patient.query.get_or_404(patient_id)
    try:
        db.session.delete(patient)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/doctor/patient/readmit', methods=['POST'])
@login_required
def readmit_patient():
    if current_user.role != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403
    
    patient_id = request.form.get('patient_id')
    patient = Patient.query.get(patient_id)
    
    if not patient:
        return jsonify({'error': 'Patient not found'}), 404
    
    try:
        patient.status = 'active'
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/doctor/patient/new', methods=['POST'])
@login_required
def handle_patient_sections():
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    section = request.form.get('section')
    patient_id = request.form.get('patient_id')

    try:
        if section == 'biodata':
            patient_type = request.form.get('patient_type')
            patient_number = generate_patient_number(patient_type)
            
            patient = Patient(
                op_number=patient_number if patient_type == 'OP' else None,
                ip_number=patient_number if patient_type == 'IP' else None,
                name=request.form.get('name'),
                age=int(request.form.get('age')) if request.form.get('age') else None,
                gender=request.form.get('gender'),
                address=request.form.get('address') if request.form.get('address') else None,
                phone=request.form.get('phone') if request.form.get('phone') else None,
                destination=request.form.get('destination'),
                occupation=request.form.get('occupation') if request.form.get('occupation') else None,
                religion=request.form.get('religion'),
                nok_name=request.form.get('nok_name') if request.form.get('nok_name') else None,
                nok_contact=request.form.get('nok_contact') if request.form.get('nok_contact') else None,
                tca=datetime.strptime(request.form.get('tca'), '%Y-%m-%d').date() if request.form.get('tca') else None,
                date_of_admission=datetime.strptime(request.form.get('date_of_admission'), '%Y-%m-%d').date() if request.form.get('date_of_admission') else date.today(),
                status='active'
            )
            db.session.add(patient)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'patient_id': patient.id,
                'next_section': 'chief_complaint'
            })

        elif section == 'chief_complaint':
            patient = Patient.query.get(patient_id)
            if not patient:
                return jsonify({'success': False, 'error': 'Patient not found'}), 404
            
            patient.chief_complaint = request.form.get('chief_complaint')
            patient.history_present_illness = request.form.get('history_present_illness')
            db.session.commit()
            
            return jsonify({
                'success': True,
                'next_section': 'review_systems'
            })

        elif section == 'review_systems':
            patient = Patient.query.get(patient_id)
            if not patient:
                return jsonify({'success': False, 'error': 'Patient not found'}), 404
            
            review = PatientReviewSystem.query.filter_by(patient_id=patient.id).first()
            if not review:
                review = PatientReviewSystem(patient_id=patient.id)
                db.session.add(review)
            
            review.cns = request.form.get('cns')
            review.cvs = request.form.get('cvs')
            review.rs = request.form.get('rs')
            review.git = request.form.get('git')
            review.gut = request.form.get('gut')
            review.skin = request.form.get('skin')
            review.msk = request.form.get('msk')
            db.session.commit()
            
            return jsonify({
                'success': True,
                'next_section': 'hpi'
            })

        elif section == 'hpi':
            patient = Patient.query.get(patient_id)
            if not patient:
                return jsonify({'success': False, 'error': 'Patient not found'}), 404
            
            patient.history_present_illness = request.form.get('hpi_details')
            db.session.commit()
            
            return jsonify({
                'success': True,
                'next_section': 'smhx'
            })

        elif section == 'smhx':
            patient = Patient.query.get(patient_id)
            if not patient:
                return jsonify({'success': False, 'error': 'Patient not found'}), 404
            
            smhx = PatientHistory.query.filter_by(patient_id=patient.id).first()
            if not smhx:
                smhx = PatientHistory(patient_id=patient.id)
                db.session.add(smhx)
            
            smhx.social_history = request.form.get('social_history')
            smhx.medical_history = request.form.get('medical_history')
            smhx.surgical_history = request.form.get('surgical_history')
            smhx.family_history = request.form.get('family_history')
            smhx.allergies = request.form.get('allergies')
            smhx.medications = request.form.get('medications')
            db.session.commit()
            
            return jsonify({
                'success': True,
                'next_section': 'examination'
            })

        elif section == 'examination':
            patient = Patient.query.get(patient_id)
            if not patient:
                return jsonify({'success': False, 'error': 'Patient not found'}), 404
            
            exam = PatientExamination.query.filter_by(patient_id=patient.id).first()
            if not exam:
                exam = PatientExamination(patient_id=patient.id)
                db.session.add(exam)
            
            exam.general_appearance = request.form.get('general_appearance')
            exam.jaundice = request.form.get('jaundice') == 'yes'
            exam.pallor = request.form.get('pallor') == 'yes'
            exam.cyanosis = request.form.get('cyanosis') == 'yes'
            exam.lymphadenopathy = request.form.get('lymphadenopathy') == 'yes'
            exam.edema = request.form.get('edema') == 'yes'
            exam.dehydration = request.form.get('dehydration') == 'yes'
            exam.dehydration_parameters = request.form.get('dehydration_parameters')
            exam.temperature = float(request.form.get('temperature')) if request.form.get('temperature') else None
            exam.pulse = int(request.form.get('pulse')) if request.form.get('pulse') else None
            exam.resp_rate = int(request.form.get('resp_rate')) if request.form.get('resp_rate') else None
            exam.bp_systolic = int(request.form.get('bp_systolic')) if request.form.get('bp_systolic') else None
            exam.bp_diastolic = int(request.form.get('bp_diastolic')) if request.form.get('bp_diastolic') else None
            exam.spo2 = int(request.form.get('spo2')) if request.form.get('spo2') else None
            exam.weight = float(request.form.get('weight')) if request.form.get('weight') else None
            exam.height = float(request.form.get('height')) if request.form.get('height') else None
            exam.bmi = float(request.form.get('bmi')) if request.form.get('bmi') else None
            exam.cvs_exam = request.form.get('cvs_exam')
            exam.resp_exam = request.form.get('resp_exam')
            exam.abdo_exam = request.form.get('abdo_exam')
            exam.cns_exam = request.form.get('cns_exam')
            exam.msk_exam = request.form.get('msk_exam')
            exam.skin_exam = request.form.get('skin_exam')
            db.session.commit()
            
            return jsonify({
                'success': True,
                'next_section': 'diagnosis'
            })

        elif section == 'diagnosis':
            patient = Patient.query.get(patient_id)
            if not patient:
                return jsonify({'success': False, 'error': 'Patient not found'}), 404
            
            diagnosis = PatientDiagnosis.query.filter_by(patient_id=patient.id).first()
            if not diagnosis:
                diagnosis = PatientDiagnosis(patient_id=patient.id)
                db.session.add(diagnosis)
            
            diagnosis.working_diagnosis = request.form.get('working_diagnosis')
            diagnosis.differential_diagnosis = request.form.get('differential_diagnosis')
            
            # Lab requests
            if request.form.getlist('lab_tests'):
                for test_id in request.form.getlist('lab_tests'):
                    lab_request = LabRequest(
                        patient_id=patient.id,
                        test_id=test_id,
                        requested_by=current_user.id,
                        status='pending',
                        notes=request.form.get('lab_notes')
                    )
                    db.session.add(lab_request)
            
            # Imaging requests
            if request.form.getlist('imaging_tests'):
                for test_id in request.form.getlist('imaging_tests'):
                    imaging_request = ImagingRequest(
                        patient_id=patient.id,
                        test_id=test_id,
                        requested_by=current_user.id,
                        status='pending',
                        notes=request.form.get('imaging_notes')
                    )
                    db.session.add(imaging_request)
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'next_section': 'management'
            })

        elif section == 'management':
            patient = Patient.query.get(patient_id)
            if not patient:
                return jsonify({'success': False, 'error': 'Patient not found'}), 404
            
            management = PatientManagement.query.filter_by(patient_id=patient.id).first()
            if not management:
                management = PatientManagement(patient_id=patient.id)
                db.session.add(management)
            
            management.treatment_plan = request.form.get('treatment_plan')
            management.follow_up = request.form.get('follow_up')
            management.notes = request.form.get('management_notes')
            
            # Prescriptions
            if request.form.getlist('drug_id'):
                for i, drug_id in enumerate(request.form.getlist('drug_id')):
                    prescription = Prescription(
                        patient_id=patient.id,
                        drug_id=drug_id,
                        doctor_id=current_user.id,
                        dosage=request.form.getlist('dosage')[i],
                        frequency=request.form.getlist('frequency')[i],
                        duration=request.form.getlist('duration')[i],
                        quantity=request.form.getlist('quantity')[i],
                        notes=request.form.getlist('prescription_notes')[i]
                    )
                    db.session.add(prescription)
            
            # Services
            if request.form.getlist('service_id'):
                for service_id in request.form.getlist('service_id'):
                    service_record = PatientService(
                        patient_id=patient.id,
                        service_id=service_id,
                        performed_by=current_user.id,
                        notes=request.form.get('service_notes')
                    )
                    db.session.add(service_record)
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'redirect': url_for('doctor_patient_details', patient_id=patient.id)
            })

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/doctor/patient/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def doctor_patient_details(patient_id):
    if current_user.role != 'doctor':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    patient = db.session.get(Patient, patient_id)
    if not patient:
        flash('Patient not found', 'danger')
        return redirect(url_for('doctor_patients'))
    
    drugs = Drug.query.filter(Drug.remaining_quantity > 0).all()
    services = Service.query.all()
    
    if request.method == 'POST':
        section = request.form.get('section')
        
        if section == 'review_systems':
            try:
                review_systems = PatientReviewSystem.query.filter_by(patient_id=patient.id).first()
                if not review_systems:
                    review_systems = PatientReviewSystem(patient_id=patient.id)
                    db.session.add(review_systems)
                
                review_systems.cns = request.form.get('cns')
                review_systems.cvs = request.form.get('cvs')
                review_systems.rs = request.form.get('rs')
                review_systems.git = request.form.get('git')
                review_systems.gut = request.form.get('gut')
                review_systems.msk = request.form.get('msk')
                
                db.session.commit()
                flash('Review of systems updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating review of systems: {str(e)}', 'danger')
        
        elif section == 'history':
            try:
                history = PatientHistory.query.filter_by(patient_id=patient.id).first()
                if not history:
                    history = PatientHistory(patient_id=patient.id)
                    db.session.add(history)
                
                history.medical_history = request.form.get('medical_history')
                history.surgical_history = request.form.get('surgical_history')
                history.family_history = request.form.get('family_history')
                history.allergies = request.form.get('allergies')
                
                db.session.commit()
                flash('Medical history updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating medical history: {str(e)}', 'danger')
        
        elif section == 'examination':
            try:
                examination = PatientExamination.query.filter_by(patient_id=patient.id).first()
                if not examination:
                    examination = PatientExamination(patient_id=patient.id)
                    db.session.add(examination)
                
                examination.general_appearance = request.form.get('general_appearance')
                examination.temperature = request.form.get('temperature')
                examination.pulse = request.form.get('pulse')
                examination.resp_rate = request.form.get('resp_rate')
                examination.bp_systolic = request.form.get('bp_systolic')
                examination.bp_diastolic = request.form.get('bp_diastolic')
                examination.spo2 = request.form.get('spo2')
                examination.cvs_exam = request.form.get('cvs_exam')
                examination.resp_exam = request.form.get('resp_exam')
                examination.abdo_exam = request.form.get('abdo_exam')
                examination.cns_exam = request.form.get('cns_exam')
                
                db.session.commit()
                flash('Examination findings updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating examination findings: {str(e)}', 'danger')
        
        elif section == 'diagnosis':
            try:
                diagnosis = PatientDiagnosis.query.filter_by(patient_id=patient.id).first()
                if not diagnosis:
                    diagnosis = PatientDiagnosis(patient_id=patient.id)
                    db.session.add(diagnosis)
                
                diagnosis.working_diagnosis = request.form.get('working_diagnosis')
                diagnosis.differential_diagnosis = request.form.get('differential_diagnosis')
                
                db.session.commit()
                flash('Diagnosis updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating diagnosis: {str(e)}', 'danger')
        

        elif section == 'management':
            try:
                # Update or create management plan
                management = PatientManagement.query.filter_by(patient_id=patient.id).first()
                if not management:
                    management = PatientManagement(patient_id=patient.id)
                    db.session.add(management)
                
                management.treatment_plan = request.form.get('treatment_plan', '')
                management.follow_up = request.form.get('follow_up', '')
                management.notes = request.form.get('management_notes', '')
                
                # Handle prescriptions
                drug_ids = request.form.getlist('drug_id')
                quantities = request.form.getlist('quantity')
                dosages = request.form.getlist('dosage')
                frequencies = request.form.getlist('frequency')
                durations = request.form.getlist('duration')
                prescription_notes = request.form.getlist('prescription_notes')
                
                # Only create prescription if there are drugs specified
                if any(drug_ids):
                    prescription = Prescription(
                        patient_id=patient.id,
                        doctor_id=current_user.id,
                        notes="Prescription from management plan",
                        status='pending'
                    )
                    db.session.add(prescription)
                    db.session.flush()  # Get the prescription ID
                    
                    for i in range(len(drug_ids)):
                        if drug_ids[i] and quantities[i]:
                            drug = db.session.get(Drug, drug_ids[i])
                            if drug:
                                prescription_item = PrescriptionItem(
                                    prescription_id=prescription.id,
                                    drug_id=drug.id,
                                    quantity=int(quantities[i]),
                                    dosage=dosages[i],
                                    frequency=frequencies[i],
                                    duration=durations[i],
                                    notes=prescription_notes[i] if i < len(prescription_notes) else None,
                                    status='pending'
                                )
                                db.session.add(prescription_item)
                                # Update drug stock
                                drug.remaining_quantity -= int(quantities[i])
                
                # Handle services
                service_ids = request.form.getlist('service_id')
                service_notes = request.form.get('service_notes', '')
                
                for service_id in service_ids:
                    if service_id:
                        service = db.session.get(Service, service_id)
                        if service:
                            patient_service = PatientService(
                                patient_id=patient.id,
                                service_id=service.id,
                                notes=service_notes,
                                requested_by=current_user.id
                            )
                            db.session.add(patient_service)
                
                db.session.commit()
                flash('Management plan updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating management plan: {str(e)}', 'danger')
        
            return redirect(url_for('doctor_patient_details', patient_id=patient_id))
    
        elif section == 'lab_request':
            try:
                test_id = request.form.get('test_id')
                if not test_id:
                    flash('Please select a test', 'danger')
                    return redirect(url_for('doctor_patient_details', patient_id=patient_id))
                
                lab_test = LabTest.query.get(test_id)
                if not lab_test:
                    flash('Lab test not found', 'danger')
                    return redirect(url_for('doctor_patient_details', patient_id=patient_id))
                
                lab_request = LabRequest(
                    patient_id=patient.id,
                    test_id=lab_test.id,
                    status='pending',
                    notes=request.form.get('notes'),
                    requested_by=current_user.id
                )
                db.session.add(lab_request)
                db.session.commit()
                
                flash('Lab request sent successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error sending lab request: {str(e)}', 'danger')
        
        elif section == 'imaging_request':
            try:
                test_id = request.form.get('test_id')
                if not test_id:
                    flash('Please select a test', 'danger')
                    return redirect(url_for('doctor_patient_details', patient_id=patient_id))
                
                imaging_test = ImagingTest.query.get(test_id)
                if not imaging_test:
                    flash('Imaging test not found', 'danger')
                    return redirect(url_for('doctor_patient_details', patient_id=patient_id))
                
                imaging_request = ImagingRequest(
                    patient_id=patient.id,
                    test_id=imaging_test.id,
                    status='pending',
                    notes=request.form.get('notes'),
                    requested_by=current_user.id
                )
                db.session.add(imaging_request)
                db.session.commit()
                
                flash('Imaging request sent successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error sending imaging request: {str(e)}', 'danger')
        
        elif request.form.get('action') == 'complete_treatment':
            try:
                patient.status = 'completed'
                patient.updated_at = datetime.utcnow()
                db.session.commit()
                flash('Patient treatment marked as completed!', 'success')
                return redirect(url_for('doctor_patients'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error completing treatment: {str(e)}', 'danger')
        
        elif request.form.get('action') == 'readmit_patient':
            try:
                patient.status = 'active'
                patient.updated_at = datetime.utcnow()
                db.session.commit()
                flash('Patient readmitted successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error readmitting patient: {str(e)}', 'danger')
        
        return redirect(url_for('doctor_patient_details', patient_id=patient_id))
    
    # Get all related data
    review_systems = PatientReviewSystem.query.filter_by(patient_id=patient.id).first()
    history = PatientHistory.query.filter_by(patient_id=patient.id).first()
    examination = PatientExamination.query.filter_by(patient_id=patient.id).first()
    diagnosis = PatientDiagnosis.query.filter_by(patient_id=patient.id).first()
    management = PatientManagement.query.filter_by(patient_id=patient.id).first()
    lab_tests = LabTest.query.all()
    imaging_tests = ImagingTest.query.all()
    lab_requests = LabRequest.query.filter_by(patient_id=patient.id).all()
    imaging_requests = ImagingRequest.query.filter_by(patient_id=patient.id).all()
    prescriptions = Prescription.query.filter_by(patient_id=patient.id).all()
    patient_services = PatientService.query.filter_by(patient_id=patient.id).all()
    
    return render_template('doctor/patient_details.html',
        patient=patient,
        review_systems=review_systems,
        history=history,
        examination=examination,
        diagnosis=diagnosis,
        management=management,
        lab_tests=lab_tests,
        imaging_tests=imaging_tests,
        lab_requests=lab_requests,
        imaging_requests=imaging_requests,
        prescriptions=prescriptions,
        patient_services=patient_services,
        drugs=drugs,
        services=services
    )

@app.route('/doctor/prescription/<int:prescription_id>')
@login_required
def doctor_prescription_details(prescription_id):
    if current_user.role != 'doctor':
        return jsonify({'error': 'Unauthorized'}), 403
    
    prescription = Prescription.query.get(prescription_id)
    if not prescription:
        return jsonify({'error': 'Prescription not found'}), 404
    
    items = [{
        'id': item.id,
        'drug_id': item.drug_id,
        'drug_name': item.drug.name,
        'quantity': item.quantity,
        'dosage': item.dosage,
        'frequency': item.frequency,
        'duration': item.duration,
        'notes': item.notes,
        'status': item.status
    } for item in prescription.items]
    
    return jsonify({
        'id': prescription.id,
        'patient_id': prescription.patient_id,
        'patient_name': prescription.patient.name if prescription.patient else '',
        'patient_number': prescription.patient.op_number or prescription.patient.ip_number if prescription.patient else '',
        'notes': prescription.notes,
        'status': prescription.status,
        'created_at': prescription.created_at.strftime('%Y-%m-%d %H:%M'),
        'items': items
    })

@app.route('/doctor/patient/complete_prescription', methods=['POST'])
@login_required
def complete_prescription():
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    patient_id = data.get('patient_id')
    prescriptions = data.get('prescriptions', [])
    
    if not patient_id:
        return jsonify({'success': False, 'error': 'Patient ID required'}), 400
    
    if not prescriptions:
        return jsonify({'success': False, 'error': 'No prescriptions provided'}), 400
    
    try:
        # Create the prescription record
        prescription = Prescription(
            patient_id=patient_id,
            doctor_id=current_user.id,
            status='pending',  # Will be changed to 'completed' when pharmacist dispenses
            notes='Prescription completed by doctor'
        )
        db.session.add(prescription)
        db.session.flush()  # Get the prescription ID
        
        # Add prescription items
        for item in prescriptions:
            drug = Drug.query.get(item['drug_id'])
            if not drug:
                continue  # Skip if drug not found
            
            prescription_item = PrescriptionItem(
                prescription_id=prescription.id,
                drug_id=drug.id,
                quantity=item['quantity'],
                dosage=item['dosage'],
                frequency=item['frequency'],
                duration=item['duration'],
                notes=item.get('notes'),
                status='pending'  # Will be changed to 'dispensed' when pharmacist processes
            )
            db.session.add(prescription_item)
        
        db.session.commit()
        
        # Log the prescription creation
        log_audit('create_prescription', 'Prescription', prescription.id, None, {
            'patient_id': patient_id,
            'items_count': len(prescriptions)
        })
        
        return jsonify({'success': True})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# Receptionist Routes
@app.route('/receptionist')
@login_required
def receptionist_dashboard():
    if current_user.role != 'receptionist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    # Calculate today's patients
    today_patients = Patient.query.filter(
        func.date(Patient.created_at) == date.today()
    ).count()
    
    # Calculate active patients
    active_patients = Patient.query.filter_by(status='active').count()
    
    # Calculate today's sales
    today_sales = db.session.query(func.sum(Sale.total_amount)).filter(
        func.date(Sale.created_at) == date.today()
    ).scalar() or 0
    
    # Calculate outstanding bills (from Debtor model)
    outstanding_bills = db.session.query(func.sum(Debtor.balance)).scalar() or 0
    
    # Get today's appointments (placeholder - you'll need to implement this)
    today_appointments = Appointment.query.filter(
        Appointment.date == date.today()
    ).count()

    pending_appointments = Appointment.query.filter(
        Appointment.status == 'scheduled'
    ).count()

    appointments = Appointment.query.filter(
        Appointment.date == date.today()
    ).order_by(Appointment.time).all()
        
    return render_template('receptionist/dashboard.html',
        today_patients=today_patients,
        active_patients=active_patients,
        today_sales=today_sales,
        outstanding_bills=outstanding_bills,
        today_appointments=today_appointments,
        pending_appointments=pending_appointments,
        appointments=appointments
    )


@app.route('/receptionist/patients')
@login_required
def receptionist_patients():
    if current_user.role != 'receptionist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    patients = Patient.query.order_by(Patient.created_at.desc()).all()
    return render_template('receptionist/patients.html', patients=patients)

@app.route('/receptionist/patient/<int:patient_id>')
@login_required
def receptionist_patient_details(patient_id):
    if current_user.role != 'receptionist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    patient = Patient.query.get(patient_id)
    if not patient:
        flash('Patient not found', 'danger')
        return redirect(url_for('receptionist_patients'))
    
    services = Service.query.all()
    lab_tests = LabTest.query.all()
    patient_labs = patient.labs
    prescriptions = patient.prescriptions
    
    # Calculate totals
    lab_total = sum(lab.test.price for lab in patient_labs)
    service_total = 0  # Will be calculated from selected services
    prescription_total = sum(
        item.drug.selling_price * item.quantity 
        for prescription in prescriptions 
        for item in prescription.items 
        if item.status == 'dispensed'
    )
    
    return render_template('receptionist/patient_details.html',
        patient=patient,
        services=services,
        lab_tests=lab_tests,
        patient_labs=patient_labs,
        prescriptions=prescriptions,
        lab_total=lab_total,
        service_total=service_total,
        prescription_total=prescription_total
    )

@app.route('/receptionist/billing', methods=['POST'])
@login_required
def create_bill():
    if current_user.role != 'receptionist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    data = request.get_json()
    patient_id = data.get('patient_id')
    service_ids = data.get('services', [])
    lab_ids = data.get('labs', [])
    
    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({'error': 'Patient not found'}), 404
    
    try:
        # Create sale
        sale = Sale(
            sale_number=generate_sale_number(),
            patient_id=patient.id,
            user_id=current_user.id,
            total_amount=0,  # Will be calculated
            payment_method=data.get('payment_method', 'cash'),
            status='completed'
        )
        db.session.add(sale)
        db.session.flush()  # To get the sale ID
        
        total_amount = 0
        
        # Add services
        for service_id in service_ids:
            service = Service.query.get(service_id)
            if service:
                sale_item = SaleItem(
                    sale_id=sale.id,
                    service_id=service.id,
                    description=service.name,
                    quantity=1,
                    unit_price=service.price,
                    total_price=service.price
                )
                db.session.add(sale_item)
                total_amount += service.price
        
        # Add lab tests
        for lab_id in lab_ids:
            lab = LabTest.query.get(lab_id)
            if lab:
                sale_item = SaleItem(
                    sale_id=sale.id,
                    lab_test_id=lab.id,
                    description=lab.name,
                    quantity=1,
                    unit_price=lab.price,
                    total_price=lab.price
                )
                db.session.add(sale_item)
                total_amount += lab.price
        
        # Add dispensed prescriptions
        prescriptions = Prescription.query.filter_by(patient_id=patient.id, status='dispensed').all()
        for prescription in prescriptions:
            for item in prescription.items:
                if item.status == 'dispensed' and item.drug:
                    sale_item = SaleItem(
                        sale_id=sale.id,
                        drug_id=item.drug.id,
                        description=f"{item.drug.name} - {item.dosage}",
                        quantity=item.quantity,
                        unit_price=item.drug.selling_price,
                        total_price=item.drug.selling_price * item.quantity
                    )
                    db.session.add(sale_item)
                    total_amount += item.drug.selling_price * item.quantity
        
        # Update sale total
        sale.total_amount = total_amount
        
        # Create transaction
        transaction = Transaction(
            transaction_number=generate_transaction_number(),
            transaction_type='sale',
            amount=total_amount,
            user_id=current_user.id,
            reference_id=sale.id
        )
        db.session.add(transaction)
        
        db.session.commit()
        
        log_audit('create_bill', 'Sale', sale.id, None, {
            'patient_id': patient.id,
            'total_amount': total_amount
        })
        
        return jsonify({
            'success': True,
            'sale_id': sale.id,
            'sale_number': sale.sale_number,
            'total_amount': total_amount
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/receptionist/sale/<int:sale_id>/receipt')
@login_required
def receptionist_receipt(sale_id):
    if current_user.role != 'receptionist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    sale = Sale.query.get(sale_id)
    if not sale:
        flash('Sale not found', 'danger')
        return redirect(url_for('receptionist_dashboard'))
    
    return render_template('receptionist/receipt.html', sale=sale)

# API Routes
@app.route('/api/drugs')
@login_required
def api_drugs():
    if current_user.role == 'admin':
        # Admin gets full drug details
        drugs = Drug.query.all()
        drugs_data = [{
            'id': drug.id,
            'drug_number': drug.drug_number,
            'name': drug.name,
            'specification': drug.specification,
            'buying_price': float(drug.buying_price),
            'selling_price': float(drug.selling_price),
            'stocked_quantity': drug.stocked_quantity,
            'sold_quantity': drug.sold_quantity,
            'expiry_date': drug.expiry_date.isoformat()
        } for drug in drugs]
        return jsonify(drugs_data)
    else:
        # Other roles get limited drug details
        search = request.args.get('search', '')
        limit = request.args.get('limit', 10, type=int)
        
        query = Drug.query.filter(Drug.remaining_quantity > 0)
        if search:
            query = query.filter(Drug.name.ilike(f'%{search}%'))
        
        drugs = query.limit(limit).all()
        
        return jsonify([{
            'id': drug.id,
            'drug_number': drug.drug_number,
            'name': drug.name,
            'specification': drug.specification,
            'selling_price': drug.selling_price,
            'remaining_quantity': drug.remaining_quantity
        } for drug in drugs])

# Add this function to generate drug numbers automatically
def generate_drug_number():
    last_drug = Drug.query.order_by(Drug.id.desc()).first()
    if last_drug:
        last_number = int(last_drug.drug_number.split('-')[-1]) if '-' in last_drug.drug_number else 0
        new_number = last_number + 1
    else:
        new_number = 1
    return f"DRG-{new_number:04d}"

@app.route('/api/drugs/<int:drug_id>')
@login_required
def api_single_drug(drug_id):
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    drug = Drug.query.get_or_404(drug_id)
    return jsonify({
        'id': drug.id,
        'drug_number': drug.drug_number,
        'name': drug.name,
        'specification': drug.specification,
        'buying_price': float(drug.buying_price),
        'selling_price': float(drug.selling_price),
        'stocked_quantity': drug.stocked_quantity,
        'expiry_date': drug.expiry_date.isoformat()
    })

@app.route('/api/drugs/stats')
@login_required
def api_drug_stats():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    total_value = db.session.query(func.sum(Drug.selling_price * (Drug.stocked_quantity - Drug.sold_quantity))).scalar() or 0
    low_stock = db.session.query(func.count(Drug.id)).filter(Drug.stocked_quantity - Drug.sold_quantity < 10).filter(Drug.stocked_quantity - Drug.sold_quantity > 0).scalar()
    expiring_soon = db.session.query(func.count(Drug.id)).filter(Drug.expiry_date <= date.today() + timedelta(days=30)).filter(Drug.expiry_date >= date.today()).scalar()
    out_of_stock = db.session.query(func.count(Drug.id)).filter(Drug.stocked_quantity - Drug.sold_quantity <= 0).scalar()
    
    return jsonify({
        'total_value': float(total_value),
        'low_stock': low_stock,
        'expiring_soon': expiring_soon,
        'out_of_stock': out_of_stock
    })

@app.route('/api/patients')
@login_required
def api_patients():
    search = request.args.get('search', '')
    limit = request.args.get('limit', 10, type=int)
    
    query = Patient.query
    if search:
        query = query.filter(
            (Patient.op_number.ilike(f'%{search}%')) |
            (Patient.ip_number.ilike(f'%{search}%')) |
            (Patient.name.ilike(f'%{search}%'))
        )
    
    patients = query.limit(limit).all()
    
    return jsonify([{
        'id': patient.id,
        'op_number': patient.op_number,
        'ip_number': patient.ip_number,
        'name': Config.decrypt_data_static(patient.name),
        'age': patient.age,
        'gender': patient.gender
    } for patient in patients])

@app.route('/receptionist/billing')
@login_required
def receptionist_billing():
    if current_user.role != 'receptionist':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('home'))
    
    patients = Patient.query.filter_by(status='active').all()
    services = Service.query.all()
    lab_tests = LabTest.query.all()
    
    return render_template('receptionist/billing.html',
        patients=patients,
        services=services,
        lab_tests=lab_tests
    )

@app.route('/api/patient/<int:patient_id>/prescriptions')
@login_required
def patient_prescriptions(patient_id):
    if current_user.role not in ['receptionist', 'doctor']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    prescriptions = Prescription.query.filter_by(
        patient_id=patient_id,
        status='pending'
    ).all()
    
    prescriptions_data = []
    for prescription in prescriptions:
        items_data = []
        for item in prescription.items:
            if item.status == 'pending' and item.drug:
                items_data.append({
                    'id': item.id,
                    'drug_id': item.drug_id,
                    'drug_name': item.drug.name,
                    'drug_number': item.drug.drug_number,
                    'quantity': item.quantity,
                    'unit_price': item.drug.selling_price,
                    'dosage': item.dosage,
                    'frequency': item.frequency,
                    'duration': item.duration
                })
        
        if items_data:  # Only include prescriptions with pending items
            prescriptions_data.append({
                'id': prescription.id,
                'patient_id': prescription.patient_id,
                'doctor_id': prescription.doctor_id,
                'doctor_name': prescription.doctor.username,
                'created_at': prescription.created_at.strftime('%Y-%m-%d %H:%M'),
                'items': items_data
            })
    
    return jsonify(prescriptions_data)

@app.route('/api/lab-tests')
@login_required
def api_lab_tests():
    search = request.args.get('search', '')
    limit = request.args.get('limit', 10, type=int)
    
    query = LabTest.query
    if search:
        query = query.filter(LabTest.name.ilike(f'%{search}%'))
    
    tests = query.limit(limit).all()
    
    return jsonify([{
        'id': test.id,
        'name': test.name,
        'price': test.price,
        'description': test.description
    } for test in tests])

@app.route('/api/services')
@login_required
def api_services():
    search = request.args.get('search', '')
    limit = request.args.get('limit', 10, type=int)
    
    query = Service.query
    if search:
        query = query.filter(Service.name.ilike(f'%{search}%'))
    
    services = query.limit(limit).all()
    
    return jsonify([{
        'id': service.id,
        'name': service.name,
        'price': service.price,
        'description': service.description
    } for service in services])

@app.route('/static/js/sw.js')
def sw():
    return send_from_directory('static/js', 'sw.js')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico')


# Error handlers
@app.errorhandler(400)
def bad_request(e):
    return render_template('errors/400.html'), 400

@app.errorhandler(401)
def unauthorized(e):
    return render_template('errors/401.html'), 401

@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403

@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return render_template('errors/405.html'), 405

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/500.html'), 500

def initialize_database():
    with app.app_context():
        # Create all database tables
        db.create_all()

app.register_blueprint(auth_bp, url_prefix='/auth')


if __name__ == '__main__':
    if not os.path.exists('instance'):
        os.makedirs('instance')
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    if not os.path.exists(app.config['BACKUP_FOLDER']):
        os.makedirs(app.config['BACKUP_FOLDER'])
        login_manager = LoginManager()
    login_manager.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))
    
    initialize_database() 
    app.run(debug=True)