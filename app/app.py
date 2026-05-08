from flask import Flask, render_template, request
import pandas as pd
import numpy as np
import joblib
import os

app = Flask(__name__)

# Load model artifacts
BASE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE, '..', 'models')

model     = joblib.load(os.path.join(MODEL_PATH, 'mediq_model.pkl'))
encoders  = joblib.load(os.path.join(MODEL_PATH, 'label_encoders.pkl'))
feat_cols = joblib.load(os.path.join(MODEL_PATH, 'feature_cols.pkl'))
threshold = joblib.load(os.path.join(MODEL_PATH, 'optimal_threshold.pkl'))

SHAP_FACTORS = [
    'change', 'utilization_score', 'num_meds_active',
    'num_meds_changed', 'number_inpatient'
]

def get_risk_level(prob):
    if prob >= 0.60:
        return 'Very High Risk', '#EF4444', '🔴'
    elif prob >= 0.40:
        return 'High Risk', '#F59E0B', '🟠'
    elif prob >= 0.25:
        return 'Medium Risk', '#3B82F6', '🟡'
    else:
        return 'Low Risk', '#10B981', '🟢'

def safe_int(val, default=0):
    """Safely convert any value to int"""
    try:
        return int(val)
    except (TypeError, ValueError):
        return default

def get_recommendations(prob, data):
    recs = []
    if prob >= 0.25:
        recs.append("Schedule follow-up appointment within 7 days")
    if safe_int(data.get('number_inpatient', 0)) >= 3:
        recs.append("Patient has multiple prior admissions — assign case manager")
    if data.get('insulin') == 'Down':
        recs.append("Review insulin dosage reduction — linked to higher readmission")
    if data.get('change') == 'Ch':
        recs.append("Medication change detected — monitor closely post-discharge")
    if safe_int(data.get('time_in_hospital', 0)) >= 7:
        recs.append("Extended hospital stay — ensure comprehensive discharge plan")
    if safe_int(data.get('number_emergency', 0)) >= 2:
        recs.append("Multiple emergency visits — high utilization patient, needs care coordinator")
    if safe_int(data.get('num_meds_active', 0)) >= 8:
        recs.append("High number of active medications — review polypharmacy risk")
    if not recs:
        recs.append("Standard discharge protocol — no immediate follow-up required")
    return recs

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    try:
        # Safely collect all form values as correct types
        age              = safe_int(request.form.get('age'), 65)
        time_in_hospital = safe_int(request.form.get('time_in_hospital'), 4)
        num_lab_proc     = safe_int(request.form.get('num_lab_procedures'), 43)
        num_procedures   = safe_int(request.form.get('num_procedures'), 1)
        num_medications  = safe_int(request.form.get('num_medications'), 15)
        num_outpatient   = safe_int(request.form.get('number_outpatient'), 0)
        num_emergency    = safe_int(request.form.get('number_emergency'), 0)
        num_inpatient    = safe_int(request.form.get('number_inpatient'), 0)
        num_diagnoses    = safe_int(request.form.get('number_diagnoses'), 7)
        num_meds_changed = safe_int(request.form.get('num_meds_changed'), 0)
        num_meds_active  = safe_int(request.form.get('num_meds_active'), 5)
        admission_type   = safe_int(request.form.get('admission_type_id'), 1)
        discharge_disp   = safe_int(request.form.get('discharge_disposition_id'), 1)
        admission_src    = safe_int(request.form.get('admission_source_id'), 7)

        utilization_score = (num_inpatient * 3) + (num_emergency * 2) + num_outpatient

        # Build data dict
        data = {
            'age_numeric'             : age,
            'time_in_hospital'        : time_in_hospital,
            'num_lab_procedures'      : num_lab_proc,
            'num_procedures'          : num_procedures,
            'num_medications'         : num_medications,
            'number_outpatient'       : num_outpatient,
            'number_emergency'        : num_emergency,
            'number_inpatient'        : num_inpatient,
            'number_diagnoses'        : num_diagnoses,
            'num_meds_changed'        : num_meds_changed,
            'num_meds_active'         : num_meds_active,
            'utilization_score'       : utilization_score,
            'race'                    : request.form.get('race', 'Caucasian'),
            'gender'                  : request.form.get('gender', 'Female'),
            'admission_type_id'       : admission_type,
            'discharge_disposition_id': discharge_disp,
            'admission_source_id'     : admission_src,
            'max_glu_serum'           : request.form.get('max_glu_serum', 'None'),
            'A1Cresult'               : request.form.get('A1Cresult', 'None'),
            'insulin'                 : request.form.get('insulin', 'No'),
            'change'                  : request.form.get('change', 'No'),
            'diabetesMed'             : request.form.get('diabetesMed', 'Yes'),
            'diag_1_category'         : request.form.get('diag_1_category', 'Circulatory'),
        }

        # Encode categoricals
        cat_cols = ['race', 'gender', 'max_glu_serum', 'A1Cresult',
                    'insulin', 'change', 'diabetesMed', 'diag_1_category']
        for col in cat_cols:
            le  = encoders[col]
            val = data[col]
            if val in le.classes_:
                data[col] = int(le.transform([val])[0])
            else:
                data[col] = 0

        # Create input dataframe
        input_df = pd.DataFrame([data])[feat_cols]

        # Predict
        prob       = float(model.predict_proba(input_df)[0][1])
        risk_level, color, emoji = get_risk_level(prob)
        recommendations = get_recommendations(prob, request.form)

        # Build risk factors list — all comparisons use safe_int
        risk_factors = []
        if num_inpatient >= 3:
            risk_factors.append(f"⚠️ {num_inpatient} prior inpatient visits — very high utilization")
        if request.form.get('insulin') == 'Down':
            risk_factors.append("⚠️ Insulin dosage reduced during visit")
        if request.form.get('change') == 'Ch':
            risk_factors.append("⚠️ Medication regimen changed during visit")
        if time_in_hospital >= 7:
            risk_factors.append(f"⚠️ {time_in_hospital} days in hospital — extended stay")
        if num_emergency >= 2:
            risk_factors.append(f"⚠️ {num_emergency} prior emergency visits")
        if utilization_score >= 10:
            risk_factors.append(f"⚠️ High hospital utilization score: {utilization_score}")
        if num_meds_active >= 8:
            risk_factors.append(f"⚠️ {num_meds_active} active medications — polypharmacy risk")
        if not risk_factors:
            risk_factors.append("✅ No major clinical risk factors detected")

        return render_template('result.html',
            prob=round(prob * 100, 1),
            risk_level=risk_level,
            color=color,
            emoji=emoji,
            recommendations=recommendations,
            risk_factors=risk_factors,
            data=request.form,
            threshold=round(threshold * 100, 1)
        )

    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)