import asyncio
from pipeline.orchestrator import run_pipeline_async

async def main():
    record = await run_pipeline_async('Siemens', '3RT2015-1BB41', 'Contactor')
    
    print('--- EXPLAINABILITY TEST ---')
    print('Status:', getattr(record, 'status', 'completed'))
    print('Overall Confidence:', getattr(record, 'overall_confidence', 'N/A'))
    
    print('\nExtracted Fields:')
    for fname, field in record.specifications.items():
        print(f"- {fname}: {field.value} (Method: {field.method}, Conf: {field.confidence})")
        if getattr(field, 'source_snippet', None):
            print(f"   Citation snippet: {field.source_snippet}")
        else:
            print(f"   Citation snippet: None (AI Inferred)")

asyncio.run(main())
