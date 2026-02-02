# Access Control System - Implementation Guide

## Overview
The hierarchical access control system restricts user access to patients based on ward and department assignments. This ensures doctors and nurses only see patients within their assigned areas of responsibility.

## Date Implemented
December 2024

## Features Implemented

### 1. Database Models

#### OutpatientDepartment
- Stores outpatient departments and clinics
- Fields: `name`, `type` (department/clinic), `description`, `is_active`
- Pre-populated departments: Pediatrics, General Medicine, Orthopedics, Surgical, Medical
- Pre-populated clinics: Diabetic, Hypertension, Cancer Screening, Ophthalmology, ENT

#### UserWardAssignment
- Many-to-many relationship between users and wards
- Fields: `user_id`, `ward_id`, `role`, `is_primary`
- Roles:
  - **Doctors**: consultant, general
  - **Nurses**: incharge, general, student, intern
- Unique constraint on (user_id, ward_id)

#### UserDepartmentAssignment
- Many-to-many relationship between users and outpatient departments
- Fields: `user_id`, `department_id`, `role`, `is_primary`
- Roles: consultant, general, specialist
- Only for doctors (outpatient department access)
- Unique constraint on (user_id, department_id)

#### Patient Model Update
- Added `department_id` foreign key to track outpatient department assignment
- Indexed for performance

### 2. Helper Functions

#### `get_user_accessible_ward_ids(user)`
Returns list of ward IDs accessible by the user based on assignments.

#### `get_user_accessible_department_ids(user)`
Returns list of department IDs accessible by the user based on assignments.

#### `filter_accessible_patients(query, user)`
Filters patient query based on user's ward and department assignments.
- Admin users see all patients
- Users with no assignments see all patients (backward compatibility)
- Doctors with ward assignments see inpatients in those wards
- Doctors with department assignments see outpatients in those departments
- Nurses with ward assignments see inpatients in those wards

#### `get_accessible_inpatients(user)`
Returns list of inpatients accessible by the user.

#### `get_accessible_outpatients(user)`
Returns list of outpatients accessible by the user.

#### `can_user_access_patient(user, patient)`
Checks if a specific user can access a specific patient.

### 3. Admin UI

#### User Management Page Updates
- **Ward Assignments Section** (for doctors and nurses)
  - Shows current ward assignments with role and primary flag
  - Add ward assignment button
  - Remove ward assignment button
  - Role selection based on user role

- **Department Assignments Section** (for doctors only)
  - Shows current department assignments with role and primary flag
  - Add department assignment button
  - Remove department assignment button

- **JavaScript Functions**
  - `showAssignmentSectionsForRole()` - Show/hide sections based on role
  - `loadUserAssignments()` - Load user's current assignments
  - `renderWardAssignments()` - Display ward assignments
  - `renderDepartmentAssignments()` - Display department assignments
  - Add/remove handlers with AJAX calls

### 4. Backend Routes

#### `/admin/wards` (GET)
Returns list of all wards for dropdown selection.

#### `/admin/departments` (GET)
Returns list of all active outpatient departments for dropdown selection.

#### `/admin/user/<user_id>/ward-assignments` (GET)
Returns user's current ward assignments with details.

#### `/admin/user/<user_id>/department-assignments` (GET)
Returns user's current department assignments with details.

#### `/admin/user/<user_id>/ward-assignment` (POST)
Adds a ward assignment for a user.
- Validates ward exists
- Prevents duplicate assignments
- Unsets other primary assignments if this is primary

#### `/admin/user/<user_id>/department-assignment` (POST)
Adds a department assignment for a user.
- Validates department exists
- Prevents duplicate assignments
- Unsets other primary assignments if this is primary

#### `/admin/user/<user_id>/ward-assignment/<assignment_id>` (DELETE)
Removes a ward assignment.

#### `/admin/user/<user_id>/department-assignment/<assignment_id>` (DELETE)
Removes a department assignment.

### 5. Updated Routes with Access Control

#### Doctor Routes
- **`/doctor`** - Dashboard filters active/completed patients by assignments
- **`/doctor/patients`** - Patient list filtered by ward/department assignments
- **`/doctor/patient/<id>`** - Medical record access checked with `can_user_access_patient()`

#### Nurse Routes
- **`/nurse`** - Dashboard filters inpatients by ward assignments
- **`/nurse/patients`** - Patient list filtered by ward assignments
- **`/nurse/patient/<id>`** - Patient details access checked with `can_user_access_patient()`

### 6. Migration File
**Location**: `migrations/versions/add_access_control.sql`

**Contents**:
1. Creates `outpatient_departments` table with indexes
2. Creates `user_ward_assignments` table with unique constraint
3. Creates `user_department_assignments` table with unique constraint
4. Adds `department_id` to `patient` table
5. Inserts default departments and clinics

## Usage Guide

### For Administrators

#### Assigning Users to Wards
1. Go to **Admin → Users**
2. Click **Edit** on a doctor or nurse
3. The **Ward Assignments** section will appear
4. Click **Add Ward Assignment**
5. Enter ward ID and role
6. Check "Primary" if this is their main ward
7. Assignment saves immediately

#### Assigning Doctors to Departments
1. Go to **Admin → Users**
2. Click **Edit** on a doctor
3. The **Department Assignments** section will appear
4. Click **Add Department Assignment**
5. Enter department ID and role
6. Check "Primary" if this is their main department
7. Assignment saves immediately

#### Removing Assignments
1. In the edit user modal, find the assignment
2. Click the **X** button next to the assignment
3. Confirm the removal

### For Doctors

#### Ward Access (Inpatients)
- Only see inpatients in assigned wards
- Can access medical records for assigned patients
- Cannot access patients in other wards

#### Department Access (Outpatients)
- Only see outpatients in assigned departments
- Can access medical records for assigned patients
- Cannot access patients in other departments

### For Nurses

#### Ward Access (Inpatients)
- Only see inpatients in assigned wards
- Can record vitals and nursing reports for assigned patients
- Cannot access patients in other wards

## Access Control Logic

### Patient Visibility Rules

1. **Admin Users**: See all patients (no restrictions)

2. **Users with No Assignments**: See all patients (backward compatibility)

3. **Inpatient Access**:
   - User must have ward assignment
   - Patient must be in a bed in that ward
   - Patient must have IP number

4. **Outpatient Access**:
   - User must have department assignment (doctors only)
   - Patient must be assigned to that department
   - Patient must have OP number

5. **Multi-Assignment Support**:
   - Doctors can be assigned to multiple wards
   - Doctors can be assigned to multiple departments
   - User sees patients from ALL assigned wards/departments

### Backward Compatibility

**If a user has no assignments**, they see all patients. This ensures:
- Existing users without assignments continue working normally
- System can be gradually rolled out
- No sudden loss of access for existing users

To enforce strict access control:
- Assign all users to appropriate wards/departments
- Users without assignments will retain full access

## Database Schema

### outpatient_departments
```sql
id INTEGER PRIMARY KEY
name VARCHAR(100) UNIQUE NOT NULL
type VARCHAR(20) CHECK (type IN ('department', 'clinic'))
description TEXT
is_active BOOLEAN DEFAULT TRUE
created_at TIMESTAMP
updated_at TIMESTAMP
```

### user_ward_assignments
```sql
id INTEGER PRIMARY KEY
user_id INTEGER REFERENCES user(id) ON DELETE CASCADE
ward_id INTEGER REFERENCES wards(id) ON DELETE CASCADE
role VARCHAR(50) NOT NULL
is_primary BOOLEAN DEFAULT FALSE
created_at TIMESTAMP
updated_at TIMESTAMP
UNIQUE (user_id, ward_id)
```

### user_department_assignments
```sql
id INTEGER PRIMARY KEY
user_id INTEGER REFERENCES user(id) ON DELETE CASCADE
department_id INTEGER REFERENCES outpatient_departments(id) ON DELETE CASCADE
role VARCHAR(50) NOT NULL
is_primary BOOLEAN DEFAULT FALSE
created_at TIMESTAMP
updated_at TIMESTAMP
UNIQUE (user_id, department_id)
```

### patient (updated)
```sql
-- Existing columns...
department_id INTEGER REFERENCES outpatient_departments(id) ON DELETE SET NULL
-- Existing columns...
```

## Testing Checklist

### Setup Phase
- [ ] Run migration SQL file to create tables
- [ ] Verify default departments and clinics inserted
- [ ] Create test wards if needed

### Admin Testing
- [ ] Edit a doctor user
- [ ] Add ward assignment (consultant role)
- [ ] Add department assignment (general role)
- [ ] Remove ward assignment
- [ ] Remove department assignment
- [ ] Verify assignments persist after page refresh

### Doctor Testing (Ward Access)
- [ ] Login as doctor with ward A assignment only
- [ ] Dashboard shows only ward A inpatients
- [ ] Patient list shows only ward A inpatients
- [ ] Can access ward A patient medical record
- [ ] Cannot access ward B patient medical record (403/redirect)

### Doctor Testing (Department Access)
- [ ] Login as doctor with pediatrics department assignment
- [ ] Dashboard shows only pediatrics outpatients
- [ ] Patient list shows only pediatrics outpatients
- [ ] Can access pediatrics patient medical record
- [ ] Cannot access orthopedics patient medical record

### Doctor Testing (Multi-Assignment)
- [ ] Assign doctor to ward A and ward B
- [ ] Verify sees inpatients from both wards
- [ ] Assign doctor to pediatrics and orthopedics
- [ ] Verify sees outpatients from both departments

### Nurse Testing
- [ ] Login as nurse with ward A assignment
- [ ] Dashboard shows only ward A inpatients
- [ ] Patient list shows only ward A inpatients
- [ ] Can access ward A patient details
- [ ] Cannot access ward B patient details
- [ ] Can record vitals for ward A patients

### Backward Compatibility Testing
- [ ] Create new doctor with NO assignments
- [ ] Verify sees ALL patients (backward compatible)
- [ ] Create new nurse with NO assignments
- [ ] Verify sees ALL patients (backward compatible)

### Edge Cases
- [ ] User assigned to empty ward sees no patients
- [ ] User assigned to ward with no beds shows empty list
- [ ] Admin can always see all patients regardless of assignments
- [ ] Deleted ward removes assignments (cascade)
- [ ] Deleted user removes assignments (cascade)

## Security Considerations

1. **Authorization Checks**: All patient access routes check `can_user_access_patient()`
2. **Admin-Only Management**: Only admins can manage ward/department assignments
3. **Cascade Deletes**: Assignments deleted when user or ward/department deleted
4. **Unique Constraints**: Prevents duplicate assignments
5. **Role Validation**: Roles validated based on user type (doctor/nurse)

## Performance Considerations

1. **Indexes**: All foreign keys indexed for fast lookups
2. **Query Optimization**: Use `filter_accessible_patients()` on base queries before ordering/limiting
3. **Relationship Caching**: SQLAlchemy relationships use lazy loading
4. **Backward Compatibility**: Users without assignments use simple queries (no joins)

## Troubleshooting

### User Cannot See Any Patients
- Check if user has ward/department assignments
- Verify assignments reference valid wards/departments
- Check if patients are actually in assigned wards/departments
- Confirm patient has bed assignment (inpatients) or department assignment (outpatients)

### User Sees Wrong Patients
- Verify assignment ward_id matches patient's bed ward_id
- Verify assignment department_id matches patient's department_id
- Check patient type (inpatient vs outpatient)

### Cannot Add Assignment
- Check if assignment already exists (unique constraint)
- Verify ward/department exists
- Check admin authorization

### Assignment Not Showing in UI
- Refresh page
- Check browser console for JavaScript errors
- Verify AJAX endpoints return correct data

## Future Enhancements

1. **Role-Based Permissions**: Different permissions per role (consultant vs general)
2. **Temporary Assignments**: Time-limited ward/department access
3. **Assignment History**: Track assignment changes over time
4. **Bulk Assignment**: Assign multiple users to a ward at once
5. **Assignment Approval**: Require admin approval for self-assignments
6. **Auto-Assignment**: Assign based on patient admission/registration

## Files Modified

### Python Files
- `app.py` - Added models, helper functions, routes, updated existing routes

### SQL Files
- `migrations/versions/add_access_control.sql` - Migration file

### Templates
- `templates/admin/users.html` - Added assignment management UI and JavaScript

## Related Documentation
- `NURSING_FEATURE_README.md` - Nursing system documentation
- `README.md` - Main project documentation

## Support
For issues or questions about the access control system, contact the development team or refer to the main project documentation.
