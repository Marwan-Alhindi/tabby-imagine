// Minimal i18n: strings are keyed by their English text, so backend-provided
// labels (plan names, confirm lines, check names) translate the same way.
let current = "en";

export const setLanguage = (l) => { current = l; };
export const lang = () => current;
const EN = {
  "cat:mobiles": "Mobiles", "cat:electronics": "Electronics", "cat:travel": "Travel", "cat:spa_salon": "Spa & Salon",
  "cat:fashion": "Fashion", "cat:beauty": "Beauty",
};
export const t = (s) => (current === "ar" ? AR[s] : EN[s]) || s;
export const sar = (n) =>
  `${Number(n).toLocaleString(current === "ar" ? "ar-SA" : "en-US", { maximumFractionDigits: 2 })} ${t("SAR")}`;

export const SUGGESTIONS = {
  ar: [
    "ابي ايفون او سامسونج ٢٥٦ جيجا وقسطه الشهري اقل من ١٠٠٠",
    "ليش ما قدرت ادفع بالفيزا حقتي؟",
    "كم باقي على أقساط السماعات؟",
    "أقدر اشتري ماك بوك اير الحين؟",
  ],
  en: [
    "iPhone or Samsung, 256GB+, under 1,000 SAR a month",
    "Why did my Visa payment fail?",
    "How many months are left on my AirPods?",
    "Can I buy a MacBook Air right now?",
  ],
};

const AR = {
  SAR: "ريال",
  "Tabby Assistant": "مساعد تابي",
  "Search, compare, pay. Just ask.": "ابحث، قارن، ادفع. بس اسأل.",
  "Hi": "هلا",
  "I can search the app, filter for you, solve payment issues, and take actions once you approve.":
    "أقدر أبحث لك في التطبيق، أفلتر لك، أحل مشاكل الدفع، وأنفذ الطلبات بعد موافقتك.",
  "Ask Tabby anything…": "اسأل تابي أي شي…",
  "Choose your language": "اختر لغتك",
  "You can change it anytime from the chat header.": "تقدر تغيرها أي وقت من أعلى المحادثة.",
  // welcome back
  "Welcome back": "هلا فيك مرة ثانية",
  "Here's where you left off:": "هذا اللي وقفت عنده:",
  "Viewed plans for": "شفت خطط",
  "Last search": "آخر بحث",
  "Checkout": "الشراء",
  "waiting for your confirmation": "بانتظار تأكيدك",
  "cancelled": "ملغي",
  "placed": "تم الطلب",
  "blocked": "متوقف",
  "Support ticket": "تذكرة دعم",
  "Also discussed": "وتكلمنا عن",
  cards: "البطاقات", payments: "المدفوعات", eligibility: "أهلية الشراء",
  "Continue": "كمّل",
  "Start new": "محادثة جديدة",
  // tool chips
  "Searching products": "أبحث عن المنتجات", "Finding deals": "أدور العروض", "Looking up stores": "أبحث عن المتاجر",
  "Comparing": "أقارن", "Calculating plans": "أحسب الخطط", "Checking your payments": "أشيك مدفوعاتك",
  "Checking your account": "أشيك حسابك", "Opening screen": "أفتح الصفحة", "Getting your invite link": "أجيب رابط الدعوة",
  "Preparing checkout": "أجهز الطلب", "Preparing payment": "أجهز الدفع", "Preparing address": "أجهز العنوان",
  "Checking your orders": "أشيك طلباتك", "Checking your cards": "أشيك بطاقاتك", "Running checkout checks": "أتحقق من أهلية الشراء",
  "Searching the help center": "أبحث في مركز المساعدة", "Preparing card change": "أجهز تغيير البطاقة",
  "Preparing support ticket": "أجهز تذكرة الدعم",
  // cards
  results: "نتيجة", "No matching products.": "ما لقيت منتجات مطابقة.", Plans: "الخطط",
  "/mo with tabby": "/شهر مع تابي", from: "من",
  "Split in 4, interest-free": "قسمها على 4، بدون فوائد",
  "Pay monthly over 6 months": "ادفع شهرياً على 6 أشهر",
  "Pay monthly over 12 months": "ادفع شهرياً على 12 شهر",
  "No interest, no fees": "بدون فوائد ولا رسوم", fee: "رسوم",
  Today: "اليوم", Total: "الإجمالي", "Last payment": "آخر دفعة", "Payment schedule": "جدول الدفعات",
  "today": "اليوم", Pay: "ادفع", "No tabby plan for this amount.": "ما فيه خطة تابي لهذا المبلغ.",
  Price: "السعر", "Monthly from": "شهرياً من", Store: "المتجر", Rating: "التقييم",
  "Due in 30 days": "المستحق خلال 30 يوم", "Total due": "الإجمالي المستحق", Available: "المتاح", due: "تستحق",
  Paid: "مدفوع", Left: "متبقي", "Next / final": "القادمة / الأخيرة", of: "من", "payment overdue": "دفعة متأخرة",
  "Your cards": "بطاقاتك", Default: "الافتراضية", Expires: "تنتهي", "Recent payments": "آخر المدفوعات",
  active: "فعالة", expired: "منتهية", succeeded: "ناجحة", failed: "فاشلة",
  "✓ You can buy this": "✓ تقدر تشتريه", "✗ Can't buy this yet": "✗ ما تقدر تشتريه الحين",
  "Amount has a Tabby plan": "المبلغ له خطة تابي", "Within available limit": "ضمن الحد المتاح",
  "No overdue payments": "ما فيه دفعات متأخرة", "Default card can be charged": "البطاقة الافتراضية صالحة",
  "Identity verified": "الهوية موثقة", Verified: "موثقة", "All payments on time": "كل الدفعات في وقتها",
  "From the help center": "من مركز المساعدة", "opened": "تم فتحها", Ticket: "تذكرة",
  "A support agent will reply in the app, usually within 24 hours.": "بيرد عليك موظف الدعم في التطبيق، غالباً خلال 24 ساعة.",
  "Cashback balance": "رصيد الكاش باك", "Profile completion": "اكتمال الملف", "Referral reward": "مكافأة الدعوة",
  "up to": "حتى", "To do": "المطلوب", "Invite friends, earn up to": "ادعُ أصحابك واكسب حتى", "Copy link": "انسخ الرابط",
  Opened: "فتحت", "cashback": "كاش باك",
  // confirm
  "Needs your approval": "يحتاج موافقتك", Cancel: "إلغاء", Approved: "تمت الموافقة", Cancelled: "تم الإلغاء",
  "Confirm purchase": "تأكيد الشراء", "Pay now": "ادفع الحين", Save: "حفظ", "Set as default": "اجعلها الافتراضية", Send: "إرسال",
  Plan: "الخطة", Then: "بعدها", Fee: "الرسوم", Card: "البطاقة", For: "لـ", "Originally due": "موعدها الأصلي",
  City: "المدينة", District: "الحي", Street: "الشارع", Building: "المبنى", "Applies to": "تطبق على",
  "All upcoming installments": "كل الأقساط القادمة", Topic: "الموضوع", Issue: "المشكلة", Reply: "الرد",
  "In the app, usually within 24 hours": "في التطبيق، غالباً خلال 24 ساعة",
  "Send to a support agent": "أرسلها لموظف الدعم", "Save home address": "حفظ عنوان المنزل",
  "Order placed": "تم الطلب", "Payment successful": "تم الدفع", "Address saved": "تم حفظ العنوان",
  "The card has expired.": "البطاقة منتهية الصلاحية.",
  "The bank reported insufficient balance.": "البنك أفاد بعدم كفاية الرصيد.",
  "OTP / 3-D Secure verification failed or timed out.": "فشل التحقق برمز OTP أو انتهى وقته.",
  Recent: "الأخيرة", Current: "الحالية", Deals: "عروض", "No recent sessions": "ما فيه محادثات حديثة",
  "Continuing where you left off": "نكمل من حيث وقفت",
  "Summaries of your last 7 days. Conversations themselves aren't shown.": "ملخصات آخر 7 أيام، بدون نص المحادثات.",
  "cat:mobiles": "جوالات", "cat:electronics": "إلكترونيات", "cat:travel": "سفر", "cat:spa_salon": "سبا وصالون",
  "cat:fashion": "أزياء", "cat:beauty": "تجميل",
  "Backup model answering": "يرد النموذج الاحتياطي",
  Home: "الرئيسية", Shop: "تسوق", Payments: "المدفوعات", Profile: "حسابي",
};
