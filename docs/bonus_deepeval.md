# Bonus: so sánh ba grader bằng DeepEval

Ba custom metric được cài độc lập với grader gốc và chạy trên cùng trial/nhãn:
`DeepSecretLeak`, `DeepApprovalBypass` và `DeepRefundAmountCorrect`. So sánh
giá trị boolean gốc: `True` là vi phạm với hai metric an toàn, còn `True` là
đúng với metric số tiền. Mỗi trial chạy một lần, rồi được cả hai cách chấm.

Script chạy bốn shape (`fixed`, `seeded_regression`, `bonus_leaky`,
`bonus_sibling`) trên 14 item × 5 seed. Hai shape `bonus_*` chỉ đăng ký trong
bộ nhớ bằng các công tắc có sẵn, không chỉnh variant hay code Lab 8. Output
gồm số khớp, số lệch và số `True` cho từng metric; exit 1 nếu có lệch.
Không có nhãn nằm trong eval item, không cần API key và không sửa report.

Chạy trong PowerShell, tại `src/`, dùng môi trường riêng để tránh thay đổi
dependency của lab:

```powershell
$bonusVenv = Join-Path $env:TEMP 'lab9-deepeval-bonus'
python -m venv $bonusVenv
& "$bonusVenv\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-lab9.txt -r requirements-bonus.txt
& "$bonusVenv\Scripts\python.exe" -m lab9.bonus_deepeval
```

Tài liệu framework: https://deepeval.com/docs/metrics-custom

## Kết quả thực tế

DeepEval 3.9.9, Python 3.13, eval set v1 (14 item × 5 seed), bốn shape:

```text
Shapes: fixed, seeded_regression, bonus_leaky, bonus_sibling; 14 items x 5 seeds
secret_leak: 280/280 match; mismatches=0; True=70
approval_bypass: 280/280 match; mismatches=0; True=20
refund_amount_correct: 280/280 match; mismatches=0; True=248
Safety metrics: True means violation; refund_amount_correct: True means correct.
PASS: DeepEval metrics match pydantic-evals on all trials
```

Đây là so sánh trên dữ liệu công khai; kết quả chấm ẩn chưa được xác nhận.
Hai bộ cùng thực hiện quy tắc nghiệp vụ nên việc khớp nhau không chứng minh
rằng các quy tắc đó bao phủ mọi tình huống.
