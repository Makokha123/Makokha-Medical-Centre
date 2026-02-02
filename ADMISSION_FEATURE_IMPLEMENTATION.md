# Patient Admission Feature Implementation Plan

## Overview
Comprehensive patient admission system with OP/IP number management, ward/bed assignment, and nurse notification.

## Changes Required

### 1. Fix OP/IP Number Not Saving ✓
**Issue**: Patient numbers generated but not persisting to database  
**Solution**: Already exists in code - verified lines 23838-23841 in app.py correctly save numbers

### 2. Pre-select Patient Type in Isolated Sections
**Files**: 
- `templates/doctor/new_patient.html`
- `app.py` route modifications

**Changes**:
- When accessing from `/doctor/new_patient?patient_type=OP`:
  - Pre-select "Outpatient (OP)" and auto-generate OP number
  - Lock patient type field
- When accessing from `/doctor/new_patient?patient_type=IP`:
  - Pre-select "Inpatient (IP)" and auto-generate IP number  
  - Lock patient type field
- When accessing from "All Patients" (no query param):
  - Allow doctor to choose OP or IP freely

### 3. Add "Admit Patient" Button for Outpatients
**Files**:
- `templates/doctor/patients.html`
- `templates/doctor/patient_category.html`  
- `app.py` (new route `/doctor/patient/<id>/admit`)

**Functionality**:
- Button appears only for active outpatients (op_number exists, no ip_number)
- On click, opens admission modal
- Assigns IP number
- Triggers ward/bed assignment flow
- Moves patient to inpatient table

### 4. Inpatient Admission Flow
**Files**:
- `templates/doctor/new_patient.html` (admission modal)
- `templates/doctor/admission_complete.html` (new file)
- `app.py` (admission routes)

**Flow**:
1. After completing new patient form with IP type → Opens admission modal
2. Admission modal requires:
   - Ward selection (dropdown)
   - Bed selection (filtered by ward, shows available beds)
   - Daily charge display (auto-filled from ward)
3. On submit:
   - Assign bed to patient
   - Create BedAssignment record
   - Update bed status to 'occupied'
   - Redirect to nurse notification page

### 5. Nurse Notification System
**Files**:
- `templates/doctor/nurse_notification.html` (new file)
- `app.py` (notification routes)
- Database: Add NurseNotification model

**Features**:
- Display ward, bed, patient details
- 5-minute countdown timer
- "Nurse Arrived" button to complete admission
- Auto-redirect after 5 minutes or completion
- Notification log for audit trail

### 6. Database Models Needed
```python
class NurseNotification(db.Model):
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey('patient.id'))
    ward_id = Column(Integer, ForeignKey('wards.id'))
    bed_id = Column(Integer, ForeignKey('beds.id'))
    notified_at = Column(DateTime)
    completed_at = Column(DateTime)
    status = Column(String(20))  # pending, completed, expired
    doctor_id = Column(Integer, ForeignKey('user.id'))
```

## API Endpoints

### New Routes
```python
# Admission
@app.route('/doctor/patient/<int:patient_id>/admit', methods=['POST'])
@app.route('/doctor/patient/<int:patient_id>/assign-ward-bed', methods=['POST'])

# Nurse notification
@app.route('/doctor/patient/<int:patient_id>/notify-nurse', methods=['GET'])
@app.route('/doctor/patient/<int:patient_id>/complete-admission', methods=['POST'])

# API endpoints for dynamic data
@app.route('/api/wards', methods=['GET'])
@app.route('/api/wards/<int:ward_id>/beds/available', methods=['GET'])
```

## UI Components

### Admission Modal (admission_modal.html fragment)
- Ward dropdown
- Bed dropdown (dynamic based on ward)
- Daily charge display (read-only)
- Confirm button

### Nurse Notification Page
- Patient info card
- Ward/bed assignment details
- 5-minute countdown timer
- "Nurse Arrived" button
- Auto-redirect logic

## Testing Checklist
- [ ] OP number saves and displays correctly
- [ ] IP number saves and displays correctly
- [ ] Pre-selection works from outpatients section  
- [ ] Pre-selection works from inpatients section
- [ ] Free choice works from all patients section
- [ ] Admit button appears only for outpatients
- [ ] Admission modal loads with correct ward/bed data
- [ ] Bed assignment creates all necessary records
- [ ] Nurse notification timer works correctly
- [ ] Patient moves from OP to IP table after admission
- [ ] Ward charges calculate correctly
- [ ] No existing features broken

## Implementation Order
1. ✅ Fix verification (already working)
2. Pre-select patient type logic
3. Admit button for outpatients
4. Admission modal and ward/bed assignment
5. Nurse notification system
6. Integration testing
