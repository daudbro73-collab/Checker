from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from services.sanctions import check_sanctions
from services.report_v2 import create_premium_pdf
from services.chain import ChainService
from services.risk_engine import calculate_risk_score
from services.graph import build_graph_data
from services.translations import get_trans
from fastapi.responses import FileResponse
import os

app = FastAPI(title="AML Service API", version="0.1.0")

# Mount static files (if any) and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/")
def read_root(request: Request, lang: str = "en"):
    trans = get_trans(lang)
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "trans": trans, 
        "lang": lang
    })

@app.get("/check")
async def check_wallet(address: str, chain: str = "ETH"):
    # 1. Check Sanctions
    sanction_result = check_sanctions(address)
    
    # 2. Get Multi-Chain Data
    chain_data = await ChainService.get_stats(chain, address)
    
    # 3. Advanced Risk Scoring
    risk_score, risk_factors, risk_level = calculate_risk_score(sanction_result, chain_data)
    
    # 4. Build Graph Data
    graph_data = build_graph_data(address, chain_data)
    
    return {
        "address": address,
        "chain": chain,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_factors": risk_factors,
        "sanctions": sanction_result,
        "details": sanction_result, # For compatibility
        "chain_data": chain_data,
        "graph_data": graph_data
    }

@app.get("/report")
async def get_report(address: str, chain: str = "ETH"):
    # Re-fetch data for report
    sanction_result = check_sanctions(address)
    chain_data = await ChainService.get_stats(chain, address)
    risk_score, risk_factors, risk_level = calculate_risk_score(sanction_result, chain_data)
    
    data = {
        "address": address,
        "chain": chain,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_factors": risk_factors,
        "sanctions": sanction_result,
        "chain_data": chain_data
    }
    
    file_path = f"report_{address}.pdf"
    create_premium_pdf(file_path, data)
    
    return FileResponse(file_path, media_type='application/pdf', filename=f"AML_Report_{address}.pdf")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
