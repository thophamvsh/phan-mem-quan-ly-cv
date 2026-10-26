"""Render the frozen v1 results without fitting or selecting new models."""
import argparse,json,sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--run",type=Path,required=True);parser.add_argument("--sensitivity",type=Path,required=True);parser.add_argument("--report",type=Path,required=True)
    args=parser.parse_args();r=json.loads((args.run/"report.json").read_text(encoding="utf-8"));m=json.loads((args.run/"manifest.json").read_text(encoding="utf-8"));s=json.loads((args.sensitivity/"report.json").read_text(encoding="utf-8"))
    predictions=pd.read_csv(args.run/"test_predictions.csv",parse_dates=["target_day"])
    fig,axes=plt.subplots(2,1,figsize=(13,8),constrained_layout=True)
    for col,label in [("actual_qve","Observed daily Qve"),("B0","B0 persistence"),("Ridge","Ridge (unqualified)")]:
        axes[0].plot(predictions.target_day,predictions[col],label=label,linewidth=1.2)
    axes[0].set(ylabel="m3/s",title="2026 partial-year holdout: retrospective SH experiment");axes[0].legend()
    folds=r["events_development"]["folds"];x=list(range(1,len(folds)+1))
    axes[1].plot(x,[f["baseline"]["mae"] for f in folds],"o-",label="Preselected baseline")
    axes[1].plot(x,[f["ridge"]["mae"] for f in folds],"o-",label="Nested Ridge")
    axes[1].set(xlabel="Candidate event fold",ylabel="Event MAE (m3/s)",title="Retrospective LOFEO (not operational backtest)");axes[1].legend()
    chart=args.run/"evaluation.png";fig.savefig(chart,dpi=150);plt.close(fig)
    table="\n".join(f"| {name} | {v['mae']:.3f} | {v['rmse']:.3f} | {v['nse']:.3f} | {v['bias']:.3f} |" for name,v in r["test_2026"].items())
    source=json.loads((args.run.parent/"source-v1.json").read_text(encoding="utf-8"))
    text=f"""# K?t qu? th? nghi?m Qv? S?ng Hinh v1 ? ch?a ??t tri?n khai ch?nh th?c

Ng?y: 26/10/2026. ??y l? k?t qu? **hindcast**, kh?ng ph?i ?? ch?nh x?c c?a m?t h? th?ng ?? ph?t h?nh d? b?o trong qu? kh?.

## D? li?u v? giao th?c

Snapshot ch? ??c c? {len(source['hydrology'])} d?ng Qv? th?y v?n, {len(source['production'])} d?ng s?n xu?t ?? l?y Qcm v? {len(source['rain'])} ng?y m?a. Dataset c? {m['rows']} l?n ph?t h?nh h?p l? theo ch?nh s?ch; kh?ng y?u c?u m?i ??c tr?ng m?a ??u ??, ? thi?u ???c gi? v? ?i?n t? train k?m c? thi?u. D? li?u g?c kh?ng thay ??i. Model ch?n nh?m `{r['selected']['group']}`, alpha={r['selected']['alpha']} b?ng validation, kh?ng b?ng test.

Ph?t h?nh 07:30 D, ??ch Qv? trung b?nh D+1. Gi? ??nh d? li?u ng?y D-1 ?? c? l?c 07:00 D. Ch?a t?i l?p ???c gi? duy?t/nh?n th?c t? l?ch s?. Nh?n Qv? d?ng Th?y v?n theo d?i; Qcm d?ng Th?ng s? s?n xu?t. Ch?a c? NWP l?ch s? ?? ??a v?o train.

Train: 2023?2024, {r['split_counts']['train']} m?u sau purge. Validation: 2025, {r['split_counts']['validation']} m?u; 20 c?u h?nh Ridge thu?c b?n nh?m ??c tr?ng. Refit tr??c test: {r['split_counts']['final_fit_development']} m?u ?? c? nh?n theo gi? ??nh tr??c l?n ph?t h?nh test ??u. Test: {r['split_counts']['test']} ng?y ??ch trong 2026. Median/scale ch? fit tr?n train c?a t?ng l??t.

## Test 2026

| M? h?nh | MAE m?/s | RMSE m?/s | NSE | Bias m?/s |
|---|---:|---:|---:|---:|
{table}

Baseline ???c ch?n tr??c khi xem test l? **{r['best_baseline_selected_on_validation']}**. B1 c? ?i?m test t?t h?n B0 kh?ng ph?i l? do ??i baseline h?u ki?m. Ridge kh?ng ??t m?c ti?u gi?m MAE 10%; m?c c?i thi?n so v?i baseline ?? ch?n l? {r['test_mae_improvement_vs_preselected_baseline']*100:.2f}% (?m ngh?a l? k?m h?n). Ridge c? xu h??ng d? b?o cao trong t?p n?y. Ch?a c? ng?y test Qv? >300 m?/s, n?n kh?ng k?t lu?n kh? n?ng d? b?o l?/??nh c?c ?oan.

Ridge t?ng t?t h?n B0 tr?n validation 2025 nh?ng kh?ng gi? ???c l?i ?ch tr?n 2026. ??y l? b?ng ch?ng c?n xem x?t ?? ?n ??nh/m?a v? th?ng tin thi?u, kh?ng ph?i l? do s?a nh?n ho?c ch?nh tham s? theo test.

## S? ki?n v? ?? nh?y

Nested LOFEO tr?n ph?n development: {len(folds)} c?m ?ng vi?n Q>300, n?i qua t?i ?a m?t ng?y th?p c? s? ?o, purge 9 ng?y hai ph?a. Ridge th?ng {sum(f['ridge']['mae']<f['baseline']['mae'] for f in folds)}/{len(folds)} fold. Trung b?nh MAE theo fold: baseline {sum(f['baseline']['mae'] for f in folds)/len(folds):.3f}, Ridge {sum(f['ridge']['mae'] for f in folds)/len(folds):.3f} m?/s. ??y l? trung b?nh ??u theo c?m, kh?ng ph?i MAE theo to?n b? ng?y. S? ki?n ch?a ???c nghi?p v? x?c nh?n v? LOFEO c? d?ng c?c s? ki?n t??ng lai c?a tr?n ???c gi?, n?n ch? l? ki?m tra kh?i qu?t h?i c?u.

K?ch b?n ch?m th?m m?t ng?y (lag=2), ??nh tr??c nh? sensitivity, cho MAE test B0={s['test_2026']['B0_persistence']['mae']:.3f}, Ridge={s['test_2026']['Ridge_selected_on_2025']['mae']:.3f}. Kh?ng ch?n k?ch b?n n?o b?ng ?i?m test.

## Ki?m tra k? thu?t v? artifact

Artifact Ridge l? JSON h? s?, median, scale v? checksum, kh?ng c?n scikit-learn l?c suy lu?n. Sai kh?c t?i ?a v?i d? b?o sklearn trong ki?m tra parity l? {r['portable_artifact_max_abs_difference']:.3g} m?/s. Ch?a benchmark Orange Pi. File model c? tr?ng th?i kh?ng ?? ?i?u ki?n production; CLI m?c ??nh tr? baseline B0 th? nghi?m, ch? d?ng Ridge khi y?u c?u r? `--allow-unqualified-ridge` cho nghi?n c?u. Thi?u l?ch s? Qv? qu? tu?i cho ph?p tr? unavailable.

Dataset CSV, manifest, snapshot ngu?n, d? b?o test v? b?o c?o JSON ???c gi? local ngo?i Git. Dataset checksum: `{m['dataset_sha256']}`. Kh?ng t?i dataset nghi?p v? ho?c credential l?n d?ch v? ngo?i.

## K?t lu?n nghi?m thu

- ??t ph?n d?ng pipeline h?i c?u, ki?m th? t?nh nh?n qu?, chu?n h?a ch? t? train v? suy lu?n portable t??ng ???ng sklearn.
- **Ch?a ??t n?ng l?c m? h?nh Ridge ?? thay baseline ho?c ??a v?o v?n h?nh ch?nh th?c.**
- Ch?a x?c minh known_at l?ch s?, s? 0/thi?u c?a m?a c?, to?n b? m?c ng?y Qcm v? kh? n?ng b?t ??nh trong test ??c l?p.
- Kh?ng hu?n luy?n l?p ?? ?u?i theo test 2026. Giai ?o?n n?y ?? ???c xem k?t qu?; c?c phi?n b?n ti?p theo c?n validation ???c thi?t k? l?i tr?n development v? m?t giai ?o?n t??ng lai m?i l?m test cu?i.

H??ng ti?p theo: x?c minh c?c ngu?n/?? tr?, duy tr? d? b?o baseline ghi tr??c k?t qu? trong ch? ?? shadow, t?ch l?y c?c ??t m?a?Qv? m?i v? forecast NWP ??ng th?i ?i?m. Ch? x?t th?m m? h?nh phi tuy?n/quantile khi c? giao th?c validation v? test m?i. Kh?ng ph?t l?nh v?n h?nh h? t? b?n th? nghi?m n?y.

Bi?u ??: [evaluation.png]({chart.resolve().as_posix()}).
"""
    args.report.write_text(text,encoding="utf-8")
    print(str(args.report));print(str(chart))


if __name__=="__main__":main()
