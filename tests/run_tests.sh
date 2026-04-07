#!/bin/bash

# 测试执行与报告生成脚本
# 用于运行所有测试并生成详细的测试报告

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TESTS_DIR="${PROJECT_ROOT}/tests"
REPORTS_DIR="${PROJECT_ROOT}/test_reports"

# 激活 conda 环境
activate_conda() {
    echo -e "${BLUE}>>> 激活 conda 环境...${NC}"
    if [ -f "/Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh" ]; then
        . /Users/test1/liuyekang/miniconda3/etc/profile.d/conda.sh
        conda activate openclaw
        echo -e "${GREEN}✓ Conda 环境激活成功${NC}"
    else
        echo -e "${RED}✗ Conda 初始化脚本不存在${NC}"
        exit 1
    fi
}

# 创建报告目录
create_report_dir() {
    echo -e "${BLUE}>>> 创建报告目录...${NC}"
    mkdir -p "${REPORTS_DIR}/htmlcov"
    mkdir -p "${REPORTS_DIR}/xml"
    echo -e "${GREEN}✓ 报告目录创建成功${NC}"
}

# 运行测试
run_tests() {
    local test_pattern="${1:-tests/}"
    
    echo -e "${BLUE}>>> 运行测试：${test_pattern}${NC}"
    echo "========================================"
    
    pytest "${test_pattern}" \
        --cov=pt_snap_cli \
        --cov-report=html:"${REPORTS_DIR}/htmlcov" \
        --cov-report=xml:"${REPORTS_DIR}/xml/coverage.xml" \
        --cov-report=term-missing \
        -v \
        --tb=short \
        "${@:2}"
    
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✓ 所有测试通过${NC}"
    else
        echo -e "${RED}✗ 部分测试失败${NC}"
    fi
    
    return $exit_code
}

# 生成报告摘要
generate_summary() {
    echo ""
    echo "========================================"
    echo -e "${BLUE}>>> 测试报告摘要${NC}"
    echo "========================================"
    
    if [ -f "${REPORTS_DIR}/xml/coverage.xml" ]; then
        echo -e "${GREEN}✓ 覆盖率报告已生成${NC}"
        echo "  - HTML 报告：${REPORTS_DIR}/htmlcov/index.html"
        echo "  - XML 报告：${REPORTS_DIR}/xml/coverage.xml"
    fi
    
    echo ""
}

# 显示帮助信息
show_help() {
    echo "用法：$0 [选项] [测试模式]"
    echo ""
    echo "选项:"
    echo "  -h, --help              显示帮助信息"
    echo "  -q, --quick             快速模式（不生成覆盖率报告）"
    echo "  -f, --file FILE         运行指定测试文件"
    echo "  -k, --keyword KEYWORD   运行匹配关键字的测试"
    echo "  -m, --mark MARK         运行标记的测试（如 slow）"
    echo "  -x, --stop              遇到失败立即停止"
    echo ""
    echo "测试模式:"
    echo "  all                     运行所有测试（默认）"
    echo "  unit                    只运行单元测试"
    echo "  integration             只运行集成测试"
    echo ""
    echo "示例:"
    echo "  $0                      # 运行所有测试并生成报告"
    echo "  $0 -q                   # 快速运行所有测试"
    echo "  $0 -f test_cli.py       # 运行指定测试文件"
    echo "  $0 -k test_render       # 运行包含关键字的测试"
    echo "  $0 -m slow              # 运行标记为 slow 的测试"
    echo "  $0 -x                   # 遇到失败立即停止"
}

# 主函数
main() {
    local quick_mode=false
    local pytest_args=()
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -q|--quick)
                quick_mode=true
                shift
                ;;
            -f|--file)
                pytest_args+=("tests/$2")
                shift 2
                ;;
            -k|--keyword)
                pytest_args+=("-k" "$2")
                shift 2
                ;;
            -m|--mark)
                pytest_args+=("-m" "$2")
                shift 2
                ;;
            -x|--stop)
                pytest_args+=("-x")
                shift
                ;;
            all)
                shift
                ;;
            unit|integration)
                echo -e "${YELLOW}警告：$1 模式暂未实现，将运行所有测试${NC}"
                shift
                ;;
            *)
                echo -e "${RED}未知选项：$1${NC}"
                echo "使用 -h 查看帮助"
                exit 1
                ;;
        esac
    done
    
    # 进入项目目录
    cd "${PROJECT_ROOT}"
    
    echo "========================================"
    echo -e "${BLUE}  测试执行与报告生成脚本${NC}"
    echo "========================================"
    echo ""
    
    # 激活环境
    activate_conda
    
    # 创建报告目录
    create_report_dir
    
    # 运行测试
    if [ "$quick_mode" = true ]; then
        echo -e "${YELLOW}>>> 快速模式：跳过覆盖率报告${NC}"
        run_tests "${pytest_args[@]}"
    else
        echo -e "${BLUE}>>> 完整模式：生成覆盖率报告${NC}"
        run_tests "${pytest_args[@]}"
    fi
    
    local test_result=$?
    
    # 生成报告摘要
    generate_summary
    
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}测试完成！${NC}"
    echo -e "${BLUE}========================================${NC}"
    
    exit $test_result
}

# 执行主函数
main "$@"
