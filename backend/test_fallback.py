import os
os.environ['SERPER_API_KEY'] = 'invalid_key'
from pipeline.retriever import retrieve
try:
    print('Testing retrieve on FRESH product...')
    res = retrieve('Schneider', 'LC1D09M7', 'Contactor', 'Electrical')
    print('Found chunks:', len(res['chunks']))
    print('MFR URL:', res.get('mfr_url'))
    print('Ref URLs:', len(res.get('ref_urls', [])))
except Exception as e:
    import traceback
    traceback.print_exc()
