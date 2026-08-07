import re


class RuleEngine:
    _PROTECTED = {
        "CPU", "GPU", "RAM", "ROM", "SSD", "HDD", "NVMe", "PCIe",
        "BIOS", "UEFI", "Docker", "Docker Compose", "Git", "GitHub",
        "VS Code", "Python", "Node.js", "Windows", "Linux", "Ubuntu",
        "Raspberry Pi", "ESP32", "Intel", "AMD", "NVIDIA", "ASUS", "MSI",
        "Gigabyte", "Kingston", "Samsung", "HP", "Dell", "Lenovo", "Acer",
    }
    _CATEGORIES = {
        "brand": ["NVIDIA", "AMD", "Intel", "Apple", "Samsung", "Sony"],
        "programming": ["Python", "C++", "Java", "JavaScript", "Go", "Rust", "TypeScript"],
    }

    def __init__(self, custom_terms=None):
        terms = set(custom_terms or [])
        for cat in self._CATEGORIES.values():
            terms.update(cat)
        terms.update(self._PROTECTED)
        self.protected = sorted(terms, key=len, reverse=True)
        self._placeholders = {}

    def mask(self, text):
        self._placeholders = {}
        for i, term in enumerate(self.protected):
            if term in text:
                placeholder = f"\x00{i}\x00"
                text = text.replace(term, placeholder)
                self._placeholders[placeholder] = term
        return text

    def unmask(self, text):
        for placeholder, term in self._placeholders.items():
            text = text.replace(placeholder, term)
        return text

    def translate_only_descriptions(self, text):
        # Stub heuristic: preserve leading labels and brand phrases.
        return text
