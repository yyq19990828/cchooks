#!/usr/bin/env python3
"""
文件模板加载器

这个模块实现了从独立文件加载模板代码，而不是使用硬编码的Python字符串。
"""

import re
from pathlib import Path
from typing import Dict, Any, Optional


class FileTemplateLoader:
    """从文件系统加载模板的加载器"""

    def __init__(self, template_base_path: Path):
        """初始化模板加载器

        Args:
            template_base_path: 模板文件基础路径
        """
        self.template_base_path = template_base_path

    def load_template_file(self, template_name: str, filename: str) -> str:
        """加载指定模板的指定文件

        Args:
            template_name: 模板名称 (如 'security_guard')
            filename: 文件名 (如 'complete_template.py')

        Returns:
            文件内容字符串
        """
        template_dir = self.template_base_path / f"{template_name}_files"
        file_path = template_dir / filename

        if not file_path.exists():
            raise FileNotFoundError(f"Template file not found: {file_path}")

        return file_path.read_text(encoding='utf-8')

    def generate_script(self, template_name: str, replacements: Optional[Dict[str, str]] = None) -> str:
        """生成完整的钩子脚本

        Args:
            template_name: 模板名称
            replacements: 可选的变量替换字典

        Returns:
            生成的脚本内容
        """
        try:
            # 加载完整模板文件
            script_content = self.load_template_file(template_name, "complete_template.py")

            # 执行变量替换
            if replacements:
                for placeholder, replacement in replacements.items():
                    # 支持 {{VAR}} 和 {VAR} 两种格式
                    pattern1 = f"{{{{{placeholder}}}}}"
                    pattern2 = f"{{{placeholder}}}"

                    script_content = script_content.replace(pattern1, replacement)
                    script_content = script_content.replace(pattern2, replacement)

            return script_content

        except FileNotFoundError as e:
            raise FileNotFoundError(f"Failed to load template '{template_name}': {e}")


def test_file_template_loader():
    """测试文件模板加载器"""
    print("🧪 测试文件模板加载器...")

    # 创建加载器
    template_path = Path("src/cchooks/templates/builtin")
    loader = FileTemplateLoader(template_path)

    try:
        # 测试加载 security-guard 模板
        script = loader.generate_script("security_guard")

        # 验证生成的脚本
        if "def main()" in script and "from cchooks import" in script:
            print("✅ 模板加载和生成成功")

            # 保存到临时文件进行语法检查
            temp_file = Path("/tmp/test_generated_security.py")
            temp_file.write_text(script, encoding='utf-8')

            # 语法检查
            import subprocess
            result = subprocess.run(
                ["python3", "-m", "py_compile", str(temp_file)],
                capture_output=True, text=True
            )

            if result.returncode == 0:
                print("✅ 生成的脚本语法正确")
                return True
            else:
                print(f"❌ 生成的脚本语法错误: {result.stderr}")
                return False
        else:
            print("❌ 生成的脚本缺少必要组件")
            return False

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


if __name__ == "__main__":
    test_file_template_loader()