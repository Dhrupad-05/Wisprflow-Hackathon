"""Create the reviewed Phase 7 routing fixture with fixed dev/test splits."""

import json
from pathlib import Path


ROWS = {
    "banking.deposit": {
        "en": ["I need a deposit", "help me save money", "I want to put money in my account", "make a cash deposit", "deposit money at SBI", "I need an SBI deposit", "please open a deposit form", "I want to add money"],
        "hi": ["मुझे जमा करना है", "पैसा जमा करना है", "खाते में पैसे डालने हैं", "नकद जमा करना है", "एसबीआई में जमा करना है", "मुझे जमा फॉर्म चाहिए", "बचत में पैसा डालना है", "जमा की मदद चाहिए"],
        "bn": ["আমার টাকা জমা দিতে হবে", "টাকা জমা করতে চাই", "অ্যাকাউন্টে টাকা দিতে চাই", "নগদ জমা দেব", "এসবিআইতে জমা দিতে চাই", "জমার ফর্ম চাই", "সঞ্চয় করতে চাই", "জমা করার সাহায্য চাই"],
        "code_mixed": ["Ami SBI te deposit korte chai", "account mein taka jama karna hai", "please টাকা জমা নিতে help করুন", "SBI mein money deposit karna hai", "amar account e deposit chai", "जमा form please", "taka save korte chai", "deposit er help lagbe"],
    },
    "agriculture.kcc_loan": {
        "en": ["I am a farmer and need a loan", "farmer credit please", "I need Kisan Credit Card", "an agriculture loan", "loan for farming", "KCC help from SBI", "credit for my crops", "farmer loan application"],
        "hi": ["मैं किसान हूं और ऋण चाहिए", "किसान क्रेडिट कार्ड चाहिए", "खेती के लिए लोन चाहिए", "कृषि ऋण की मदद चाहिए", "फसल के लिए कर्ज चाहिए", "एसबीआई किसान लोन", "किसान ऋण फॉर्म", "खेती का क्रेडिट चाहिए"],
        "bn": ["আমি কৃষক, আমার ঋণ লাগবে", "কিষান ক্রেডিট কার্ড চাই", "চাষের জন্য ঋণ চাই", "কৃষি ঋণের সাহায্য চাই", "ফসলের জন্য ধার চাই", "এসবিআই কৃষক ঋণ", "কৃষক ঋণের ফর্ম চাই", "চাষের ক্রেডিট দরকার"],
        "code_mixed": ["Ami chashi amar loan lagbe", "farmer ke liye KCC chahiye", "krishi loan er help chai", "SBI farmer credit please", "chash er jonno loan chai", "Kisan credit form do", "amar crop loan lagbe", "किसान loan चाहिए"],
    },
    "msme.msme_loan": {
        "en": ["I need a business loan", "loan for my small business", "MSME credit for my unit", "working capital for business", "shop expansion loan", "enterprise finance please", "business funding help", "loan for my company"],
        "hi": ["मुझे व्यवसाय ऋण चाहिए", "छोटे कारोबार के लिए लोन चाहिए", "एमएसएमई क्रेडिट चाहिए", "दुकान बढ़ाने का ऋण चाहिए", "व्यापार के लिए पूंजी चाहिए", "कंपनी फंडिंग चाहिए", "कारोबार लोन फॉर्म", "उद्यम के लिए ऋण"],
        "bn": ["আমার ব্যবসার ঋণ দরকার", "ছোট ব্যবসার জন্য লোন চাই", "এমএসএমই ক্রেডিট চাই", "দোকান বাড়ানোর ঋণ চাই", "ব্যবসার মূলধন দরকার", "কোম্পানির ফান্ডিং চাই", "ব্যবসার ঋণের ফর্ম চাই", "উদ্যোগের জন্য ঋণ চাই"],
        "code_mixed": ["business ke liye loan chahiye", "amar small business er loan lagbe", "MSME credit please", "shop expand karne ka loan", "ব্যবসার loan চাই", "company ke liye funding do", "udhyam business loan", "কারবারের জন্য loan chai"],
    },
    "msme.udyam": {
        "en": ["I need Udyam registration", "register my business", "MSME registration help", "business registration form", "get an enterprise certificate", "I want to register my company", "small business registration", "Udyam application"],
        "hi": ["उद्यम पंजीकरण चाहिए", "मेरा व्यवसाय रजिस्टर करना है", "एमएसएमई पंजीकरण मदद", "व्यापार पंजीकरण फॉर्म", "उद्यम प्रमाणपत्र चाहिए", "कंपनी पंजीकरण करना है", "छोटे कारोबार का पंजीकरण", "उद्यम आवेदन चाहिए"],
        "bn": ["উদ্যোগ রেজিস্ট্রেশন চাই", "আমার ব্যবসা নিবন্ধন করতে চাই", "এমএসএমই নিবন্ধনের সাহায্য চাই", "ব্যবসার নিবন্ধন ফর্ম চাই", "উদ্যোগ সার্টিফিকেট চাই", "কোম্পানি রেজিস্ট্রেশন করব", "ছোট ব্যবসা নিবন্ধন", "উদ্যোগের আবেদন চাই"],
        "code_mixed": ["Udyam registration karna hai", "amar business register korte chai", "MSME registration please", "company ka udyam form", "ব্যবসা registration help", "enterprise certificate chahiye", "small business register karna hai", "উদ্যোগ form চাই"],
    },
    "social_welfare.widow_pension": {
        "en": ["I need widow pension", "pension for a widow", "help with widow benefits", "social welfare widow form", "my widow pension application", "widow support scheme", "apply for widow pension", "widow allowance help"],
        "hi": ["विधवा पेंशन चाहिए", "विधवा के लिए पेंशन", "विधवा लाभ की मदद", "विधवा पेंशन फॉर्म", "मेरी विधवा पेंशन", "विधवा सहायता योजना", "विधवा पेंशन आवेदन", "विधवा भत्ता चाहिए"],
        "bn": ["বিধবা পেনশন চাই", "বিধবার জন্য পেনশন", "বিধবা ভাতার সাহায্য চাই", "বিধবা পেনশনের ফর্ম", "আমার বিধবা পেনশন", "বিধবা সহায়তা প্রকল্প", "বিধবা পেনশনের আবেদন", "বিধবা ভাতা চাই"],
        "code_mixed": ["widow pension chahiye", "amar widow pension lagbe", "विधवा pension help", "বিধবা pension form chai", "widow benefits ke liye help", "pension for widow please", "vidhwa scheme batao", "বিধবা allowance চাই"],
    },
    "social_welfare.old_age_pension": {
        "en": ["I need old age pension", "senior citizen pension", "pension for my elderly parent", "old age benefits help", "apply for age pension", "elder welfare pension", "my old age pension form", "retirement support scheme"],
        "hi": ["वृद्धावस्था पेंशन चाहिए", "बुजुर्ग पेंशन चाहिए", "मेरे माता पिता की पेंशन", "बुढ़ापे के लाभ की मदद", "आयु पेंशन आवेदन", "वरिष्ठ नागरिक पेंशन", "वृद्ध पेंशन फॉर्म", "बुजुर्ग सहायता योजना"],
        "bn": ["বৃদ্ধ বয়সের পেনশন চাই", "বয়স্ক নাগরিকের পেনশন", "বাবা মায়ের পেনশন চাই", "বৃদ্ধ ভাতার সাহায্য চাই", "বয়স পেনশনের আবেদন", "বয়স্ক পেনশন ফর্ম", "প্রবীণ সহায়তা প্রকল্প", "বৃদ্ধ পেনশন দরকার"],
        "code_mixed": ["old age pension chahiye", "amar elderly parent er pension lagbe", "বৃদ্ধ pension help", "senior citizen pension form", "बुजुर्ग pension चाहिए", "age benefit er help chai", "old pension apply karna hai", "বয়স্ক scheme চাই"],
    },
    "civil_services.ration_card": {
        "en": ["I need a ration card", "apply for ration card", "food card help", "ration application for my family", "new ration card form", "government food card", "ration card correction", "help with ration service"],
        "hi": ["राशन कार्ड चाहिए", "राशन कार्ड के लिए आवेदन", "खाद्य कार्ड की मदद", "परिवार का राशन आवेदन", "नया राशन कार्ड फॉर्म", "सरकारी राशन कार्ड", "राशन कार्ड सुधार", "राशन सेवा में मदद"],
        "bn": ["রেশন কার্ড চাই", "রেশন কার্ডের আবেদন", "খাদ্য কার্ডের সাহায্য চাই", "পরিবারের রেশন আবেদন", "নতুন রেশন কার্ড ফর্ম", "সরকারি খাদ্য কার্ড", "রেশন কার্ড সংশোধন", "রেশন পরিষেবার সাহায্য"],
        "code_mixed": ["ration card chahiye", "amar ration card apply korte chai", "খাদ্য card help চাই", "family ke liye ration form", "राशन card correction", "food card er help chai", "new ration card please", "রেশন service চাই"],
    },
}


def repair_encoding(value: str) -> str:
    """Recover native-script strings stored as UTF-8 decoded as CP1252."""
    if not any(marker in value for marker in ("à", "á", "â")):
        return value
    try:
        return value.encode("latin1").decode("utf-8")
    except UnicodeError:
        return value


def main():
    output = Path(__file__).parents[1] / "tests" / "eval" / "utterances.jsonl"
    rows = []
    for label, languages in ROWS.items():
        for language, texts in languages.items():
            for index, text in enumerate(texts):
                text = repair_encoding(text)
                rows.append({"text": text, "label": label, "language": language, "split": "dev" if index < 4 else "test", "named_entity": any(token in text.lower() for token in ["sbi", "kcc", "udyam", "msme", "किसान", "এসবিআই"])})
    output.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} rows to {output}")


if __name__ == "__main__":
    main()
