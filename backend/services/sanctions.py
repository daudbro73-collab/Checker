def check_sanctions(address: str):
    # In a real app, this would load a massive local DB or query an external API.
    # For now, we simulate with a known hacked address list (e.g., Lazarus Group addresses).
    
    BLACKLIST = {
        "0x53b6936513e738f44fb50d2b9476730c0ab3bfc1": {"source": "OFAC", "reason": "Lazarus Group"},
        "0xa09871aeadf4994ca12f5c0b6056bbd1d343c029": {"source": "HACK", "reason": "Ronin Bridge Exploiter"},
        "0xd90e2f925da726b50c4ed8d0fb90ad053324f31b": {"source": "OFAC", "reason": "Tornado Cash"}
    }
    
    address_lower = address.lower()
    if address_lower in BLACKLIST:
        return {
            "is_sanctioned": True, 
            "source": BLACKLIST[address_lower]["source"],
            "reason": BLACKLIST[address_lower]["reason"]
        }
    
    return {"is_sanctioned": False, "source": None, "reason": None}
