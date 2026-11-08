# Demonstration Dataset - Ground Truth

All documents are fully synthetic. No real person, PAN, account or photograph is used.

Deterministic seed: 20261109

## Genuine packet (`dataset/genuine/`)

An internally consistent loan / KYC packet. Expected findings: 0 high-confidence anomalies.

## Manipulated packet (`dataset/manipulated/`)

The same packet with the following planted anomalies:

| ID | Class | Documents | Detail | Expected confidence |
|----|-------|-----------|--------|---------------------|
| A1_dob_mismatch | cross_document | id, application | DOB on PAN ID (14-03-1990) conflicts with application form (14-03-1992). | high |
| A2_income_inflation | cross_document | application, salary_slip, bank_statement | Declared monthly income on application (INR 140,000) exceeds salary-slip net pay and bank salary credit (INR 86,000). | high |
| A3_balance_arithmetic | structural | bank_statement | Printed closing balance does not equal opening balance plus the sum of ledger transactions. | high |
| A4_address_mismatch | cross_document | address_proof, application | Address on utility bill (12 Park Street) conflicts with application address (48 Camac Street). | high |
| A5_pdf_incremental | pdf_forensic | bank_statement | Bank statement PDF contains an incremental-update revision after signing, and creator/producer disagree. | high |
| A6_photo_splice | visual_forensic | id | ID photo region shows duplicated (copy-move) texture and EXIF Software tag indicates photo-editing software. | medium |
| A7_employer_mismatch | cross_document | salary_slip, application | Employer on salary slip (Nimbus Data Labs LLP) differs from application (Nimbus Analytics Pvt Ltd). | medium |
| A8_date_logic | cross_document | id, application | PAN issue date (22-07-2027) is after the application date (05-09-2026), which is impossible. | high |

Classes: cross_document (contextual correlation), structural (within-document arithmetic/logic),
pdf_forensic (born-digital PDF tamper), visual_forensic (image-level, reported at low/medium confidence).