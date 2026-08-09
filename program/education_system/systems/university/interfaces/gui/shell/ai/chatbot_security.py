"""Central security policy for university chatbot requests and responses."""
from __future__ import annotations
import hashlib, hmac, json, os, re, secrets, time
from pathlib import Path
from education_system.platform.governance.security.rate_limiter import PersistentRateLimiter
from education_system.paths import UNIVERSITY_CHATBOT_DATA_DIR

class SecurityViolation(RuntimeError): pass

class ChatbotSecurityPolicy:
    READ_TOOLS=frozenset({'balance','holds','grade','timeline','period','rooms','documents','messages','module_summary'})
    MUTATION_TOOLS=frozenset({'book_room','send_message','submit_request','update_record','delete_record'})
    INJECTION=(r'ignore\s+(all\s+)?previous',r'reveal\s+(the\s+)?system prompt',r'override\s+(your|the)\s+rules')
    SECRET=re.compile(r'(?i)(api[_ -]?key|password|secret|token)\s*[:=]\s*\S+')
    BULK_PII=re.compile(r'(?i)(?:\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b.*){5,}')
    def __init__(self, username, role='student'):
        self.username=str(username); self.role=str(role); self.limiter=PersistentRateLimiter()
        self.tokens={}; self.audit_path=UNIVERSITY_CHATBOT_DATA_DIR/'security_audit.jsonl'; self.audit_path.parent.mkdir(parents=True,exist_ok=True)
    def enabled(self): return os.getenv('CHATBOT_KILL_SWITCH','0') not in {'1','true','yes'}
    def validate_request(self,message):
        if not self.enabled(): raise SecurityViolation('The assistant is temporarily disabled by an administrator.')
        if not isinstance(message,str) or not 1<=len(message)<=10000: raise SecurityViolation('Invalid message length.')
        allowed,retry=self.limiter.check_rate_limit(f'chatbot:user:{self.username}',30,60)
        if not allowed: raise SecurityViolation(f'Too many requests. Retry in {retry} seconds.')
        if any(re.search(p,message,re.I) for p in self.INJECTION): raise SecurityViolation('Potential prompt-injection instructions were blocked.')
        self.audit('request_allowed',{'length':len(message)})
    def authorize_record(self,subject_id,purpose='support'):
        if self.role not in {'admin','staff'} and str(subject_id)!=self.username: raise SecurityViolation('You are not authorised to access that record.')
        self.audit('record_access',{'subject':str(subject_id),'purpose':purpose})
    def authorize_tool(self,name,mutating=False):
        allowed=self.MUTATION_TOOLS if mutating else self.READ_TOOLS
        if name not in allowed: raise SecurityViolation('That assistant tool is not approved.')
    def issue_action_token(self,action,ttl=120):
        raw=secrets.token_urlsafe(24); self.tokens[hashlib.sha256(raw.encode()).hexdigest()]=(action,time.time()+ttl); return raw
    def consume_action_token(self,raw,action):
        item=self.tokens.pop(hashlib.sha256(raw.encode()).hexdigest(),None)
        if not item or item[0]!=action or item[1]<time.time(): raise SecurityViolation('Action confirmation expired.')
    def sanitize_output(self,text):
        text=self.SECRET.sub('[REDACTED]',str(text))
        if self.BULK_PII.search(text): raise SecurityViolation('The response was blocked by data-loss prevention.')
        return text
    def audit(self,event,details):
        previous='0'*64
        if self.audit_path.exists():
            try: previous=json.loads(self.audit_path.read_text().splitlines()[-1])['hash']
            except Exception: pass
        record={'time':int(time.time()),'user':self.username,'event':event,'details':details,'previous':previous}
        record['hash']=hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()
        with self.audit_path.open('a',encoding='utf-8') as f: f.write(json.dumps(record,sort_keys=True)+'\n')

def secure_headers():
    return {'Strict-Transport-Security':'max-age=31536000; includeSubDomains','Content-Security-Policy':"default-src 'self'; object-src 'none'; frame-ancestors 'none'",'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Permissions-Policy':'camera=(), geolocation=()'}
