"""Demo case creation for first-time users"""

from ..models import Case, Evidence, Note


def create_demo_case() -> Case:
    """Create a demo case with evidence showcasing all features"""
    demo_case = Case(
        case_number="DEMO-2024-001",
        name="Sample Investigation",
        investigator="Demo User"
    )

    # Add case-level notes to demonstrate case notes feature
    case_note1 = Note(content="""Initial case briefing: Suspected data exfiltration incident.

Key objectives:
- Identify compromised systems
- Determine scope of data loss
- Document timeline of events

#incident-response #data-breach #investigation""")
    case_note1.calculate_hash()
    case_note1.extract_tags()
    case_note1.extract_iocs()
    demo_case.notes.append(case_note1)

    case_note2 = Note(content="""Investigation lead: Employee reported suspicious email from sender@phishing-domain.com
Initial analysis shows potential credential harvesting attempt.
Review email headers and attachments for IOCs. #phishing #email-analysis""")
    case_note2.calculate_hash()
    case_note2.extract_tags()
    case_note2.extract_iocs()
    demo_case.notes.append(case_note2)

    # Create evidence 1: Compromised laptop
    evidence1 = Evidence(
        name="Employee Laptop HDD",
        description="Primary workstation hard drive - user reported suspicious activity"
    )
    # Add source hash for chain of custody demonstration
    evidence1.metadata["source_hash"] = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    # Add notes to evidence 1 with various features
    note1 = Note(content="""Forensic imaging completed. Drive imaged using FTK Imager.
Image hash verified: SHA256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

Chain of custody maintained throughout process. #forensics #imaging #chain-of-custody""")
    note1.calculate_hash()
    note1.extract_tags()
    note1.extract_iocs()
    evidence1.notes.append(note1)

    note2 = Note(content="""Discovered suspicious connections to external IP addresses:
- 192.168.1.100 (local gateway)
- 203.0.113.45 (external, geolocation: Unknown)
- 198.51.100.78 (command and control server suspected)

Browser history shows visits to malicious-site.com and data-exfil.net.
#network-analysis #ioc #c2-server""")
    note2.calculate_hash()
    note2.extract_tags()
    note2.extract_iocs()
    evidence1.notes.append(note2)

    note3 = Note(content="""Malware identified in temp directory:
File: evil.exe
MD5: d41d8cd98f00b204e9800998ecf8427e
SHA1: da39a3ee5e6b4b0d3255bfef95601890afd80709
SHA256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

Submitting to VirusTotal for analysis. #malware #hash-analysis #virustotal""")
    note3.calculate_hash()
    note3.extract_tags()
    note3.extract_iocs()
    evidence1.notes.append(note3)

    note4 = Note(content="""Timeline analysis reveals:
- 2024-01-15 09:23:45 - Suspicious email received
- 2024-01-15 09:24:12 - User clicked phishing link https://evil-domain.com/login
- 2024-01-15 09:25:03 - Credentials submitted to attacker-controlled site
- 2024-01-15 09:30:15 - Lateral movement detected

User credentials compromised. Recommend immediate password reset. #timeline #lateral-movement""")
    note4.calculate_hash()
    note4.extract_tags()
    note4.extract_iocs()
    evidence1.notes.append(note4)

    demo_case.evidence.append(evidence1)

    # Create evidence 2: Network logs
    evidence2 = Evidence(
        name="Firewall Logs",
        description="Corporate firewall logs from incident timeframe"
    )
    evidence2.metadata["source_hash"] = "a3f5c8b912e4d67f89b0c1a2e3d4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2"

    note5 = Note(content="""Log analysis shows outbound connections to suspicious domains:
- attacker-c2.com on port 443 (encrypted channel)
- data-upload.net on port 8080 (unencrypted)
- exfil-server.org on port 22 (SSH tunnel)

Total data transferred: approximately 2.3 GB over 4 hours.
#log-analysis #data-exfiltration #network-traffic""")
    note5.calculate_hash()
    note5.extract_tags()
    note5.extract_iocs()
    evidence2.notes.append(note5)

    note6 = Note(content="""Contact information found in malware configuration:
Email: attacker@malicious-domain.com
Backup C2: 2001:0db8:85a3:0000:0000:8a2e:0370:7334 (IPv6)

Cross-referencing with threat intelligence databases. #threat-intel #attribution""")
    note6.calculate_hash()
    note6.extract_tags()
    note6.extract_iocs()
    evidence2.notes.append(note6)

    demo_case.evidence.append(evidence2)

    # Create evidence 3: Email forensics
    evidence3 = Evidence(
        name="Phishing Email",
        description="Original phishing email preserved in .eml format"
    )

    note7 = Note(content="""Email headers analysis:
From: sender@phishing-domain.com (spoofed)
Reply-To: attacker@evil-mail-server.net
X-Originating-IP: 198.51.100.99

Email contains embedded tracking pixel at http://tracking.malicious-site.com/pixel.gif
Attachment: invoice.pdf.exe (double extension trick) #email-forensics #phishing-analysis""")
    note7.calculate_hash()
    note7.extract_tags()
    note7.extract_iocs()
    evidence3.notes.append(note7)

    demo_case.evidence.append(evidence3)

    return demo_case
