import copy,json,sys,tempfile,hashlib,platform
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'scripts'))
import nbformat
from verify_learning_labs import derive_variant,run_notebook,prepare_workspace,independently_check_metrics,FIXTURE_DIR
source=ROOT/'notebooks/labs/lab-imbalanced-classification.ipynb'
lab=json.loads((ROOT/'content/learning/labs/lab-imbalanced-classification.json').read_text())
report=json.loads((ROOT/'content/learning/evidence/assessment/lab-l0-l3-execution-20260907.json').read_text())
assert report['inputs']['sourceNotebook']=='sha256:'+hashlib.sha256(source.read_bytes()).hexdigest()
notebook=derive_variant('solution')
notebook.cells.append(nbformat.v4.new_code_cell('''audit = {"actualKernelPython":sys.version.split()[0],"actualPackages":{"numpy":np.__version__,"pandas":pd.__version__,"scikit-learn":sklearn.__version__},"fitRows":len(fit_row_ids),"actualWrongFitRows":len(leaky_fit_row_ids),"actualWrongSelectionRows":len(test_selection_row_ids),"correctSelectionRows":len(threshold_selection_row_ids),"wrongFitIncludesTest":bool(set(leaky_fit_row_ids)&split_ids["test"]),"wrongSelectionEqualsTest":set(test_selection_row_ids)==split_ids["test"]}
Path("independent-audit.json").write_text(json.dumps(audit))
'''))
with tempfile.TemporaryDirectory(prefix='ipas-independent-l4-') as raw:
 cwd=Path(raw);prepare_workspace(cwd,root_upload=True)
 _,seconds=run_notebook(notebook,cwd)
 metrics=json.loads((cwd/'metrics.json').read_text());audit=json.loads((cwd/'independent-audit.json').read_text())
 assert not (cwd/'fixtures').exists()
 split=json.loads((FIXTURE_DIR/'split_manifest_v1.json').read_text());data=FIXTURE_DIR/'equipment_alerts_v1.csv'
 independently_check_metrics(metrics,split,data)
 probes={
 'empty_fit_rows':lambda m:m.update(fitRowIds=[]),
 'test_row_identity':lambda m:m['test']['rowIds'].__setitem__(0,'invented'),
 'only_two_test_labels':lambda m:m['test'].update(yTrue=[0,1],yPred=[0,1]),
 'negative_validation_cost':lambda m:m['validationTable'][0].update(average_cost=-100),
 'impossible_validation_recall':lambda m:m['validationTable'][0].update(recall=99),
 'changed_fn5_cost':lambda m:m['sensitivityFn5']['validationTable'][0].update(average_cost=-1),
 'forged_dummy_metric':lambda m:m['test']['dummy'].update(recall=1),
 'changed_threshold':lambda m:m.update(threshold=-1),
 }
 outcomes={}
 for name,mutate in probes.items():
  candidate=copy.deepcopy(metrics);mutate(candidate)
  try:independently_check_metrics(candidate,split,data)
  except (AssertionError,ValueError,KeyError):outcomes[name]='rejected'
  else:raise AssertionError('UNREJECTED: '+name)
 assert audit['actualKernelPython']==report['environment']['python']
 assert audit['actualKernelPython'].startswith(lab['environment']['pythonVersion']+'.')
 assert audit['actualPackages']=={k:report['environment']['packages'][k] for k in audit['actualPackages']}
 assert (audit['fitRows'],audit['actualWrongFitRows'],audit['correctSelectionRows'],audit['actualWrongSelectionRows'])==(1200,2000,400,400)
 assert audit['wrongFitIncludesTest'] and audit['wrongSelectionEqualsTest']
 assert metrics['test']['dummy']['recall']==0 and metrics['test']['dummy']['accuracy']==.95
 starter=derive_variant('starter');byid={c.id:c for c in starter.cells}
 assert 'solution-note' not in byid
 assert 'raise NotImplementedError' in byid['threshold-and-artifacts'].source
 assert 'Path("metrics.json").write_text' in byid['threshold-and-artifacts'].source
 assert 'assert_result(result)' in byid['invariant-and-fault-checks'].source
 assert 'test_scores' not in byid['fit-train-only'].source
 s=byid['threshold-and-artifacts'].source;assert s.index('frozen_threshold =')<s.index('test_scores =')
 output={'verdict':'pass','reviewerId':'agent-content-labs','role':'independent_model','scope':'L4 semantic and independent fault checks; no human Colab','sourceHash':report['inputs']['sourceNotebook'],'labContentHash':lab['contentHash'],'executionSeconds':round(seconds,3),'rootUploadWithoutFixturesDirectory':True,'audit':audit,'probes':outcomes,'baseline':metrics['test']['dummy'],'selectedThreshold':metrics['threshold'],'testMetrics':{k:metrics['test'][k] for k in ['tn','fp','fn','tp','accuracy','precision','recall','f1','average_cost']},'humanL5':'not_run'}
 output['baseline'].pop('yPred')
 Path('/tmp/ipas-l4-independent-result.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(output,ensure_ascii=False,indent=2))
