
-- =====================================================
-- MedIQ — Hospital Analytics SQL Queries
-- =====================================================

-- Q1: Patient Risk Stratification
SELECT 
    CASE 
        WHEN number_inpatient >= 5 THEN 'Very High Risk'
        WHEN number_inpatient >= 3 THEN 'High Risk'
        WHEN number_inpatient >= 1 THEN 'Medium Risk'
        ELSE 'Low Risk'
    END AS risk_tier,
    COUNT(*) AS total_patients,
    SUM(readmitted_binary) AS readmissions,
    ROUND(AVG(readmitted_binary) * 100, 2) AS readmission_rate_pct,
    ROUND(AVG(time_in_hospital), 2) AS avg_days_in_hospital,
    ROUND(AVG(num_medications), 2) AS avg_medications
FROM patients
GROUP BY risk_tier
ORDER BY readmission_rate_pct DESC;

-- Q2: Department Analysis
SELECT medical_specialty,
    COUNT(*) AS total_patients,
    ROUND(AVG(readmitted_binary) * 100, 2) AS readmission_rate_pct,
    ROUND(AVG(time_in_hospital), 2) AS avg_stay_days
FROM patients
WHERE medical_specialty != 'Unknown'
GROUP BY medical_specialty
HAVING total_patients >= 100
ORDER BY readmission_rate_pct DESC
LIMIT 15;

-- Q3: Medication Change Impact (CTE)
WITH medication_profile AS (
    SELECT 
        CASE 
            WHEN num_meds_changed = 0 THEN 'No Change'
            WHEN num_meds_changed = 1 THEN '1 Med Changed'
            WHEN num_meds_changed = 2 THEN '2 Meds Changed'
            ELSE '3+ Meds Changed'
        END AS med_change_group,
        readmitted_binary, time_in_hospital, num_medications
    FROM patients
)
SELECT med_change_group, COUNT(*) AS total_patients,
    ROUND(AVG(readmitted_binary) * 100, 2) AS readmission_rate_pct
FROM medication_profile
GROUP BY med_change_group
ORDER BY readmission_rate_pct DESC;

-- Q4: Highest Risk Age Group per Diagnosis (RANK)
WITH patient_segments AS (
    SELECT diag_1_category, age,
        ROUND(AVG(readmitted_binary)*100,2) AS readmission_rate,
        COUNT(*) AS patient_count
    FROM patients
    GROUP BY diag_1_category, age
    HAVING patient_count >= 50
),
ranked AS (
    SELECT *, RANK() OVER (
        PARTITION BY diag_1_category
        ORDER BY readmission_rate DESC
    ) AS risk_rank FROM patient_segments
)
SELECT * FROM ranked WHERE risk_rank = 1
ORDER BY readmission_rate DESC;

-- Q5: Readmission by Admission Type (LAG)
WITH admission_stats AS (
    SELECT admission_type_id,
        COUNT(*) AS total_patients,
        ROUND(AVG(readmitted_binary)*100,2) AS readmission_rate
    FROM patients GROUP BY admission_type_id
)
SELECT *, LAG(readmission_rate) OVER (ORDER BY readmission_rate DESC) AS prev_rate,
    ROUND(readmission_rate - LAG(readmission_rate)
        OVER (ORDER BY readmission_rate DESC),2) AS rate_diff
FROM admission_stats
ORDER BY readmission_rate DESC;
