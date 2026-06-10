# StudentPickerDialog 设计说明

## 目标

`StudentPickerDialog` 用于替代教师端所有“学生多选下拉”。下拉适合少量选项，不适合真实班级场景；当学生达到几十人甚至更多时，需要搜索、筛选、分页和已选名单管理。

当前已接入：

- 创建班级
- 创建学习路径任务
- 发布普通教学任务

## 交互结构

```text
┌──────────────────────────────────────────┬────────────────────┐
│ 搜索 / 年级 / 专业 / 状态 / 搜索按钮      │ 已选学生             │
├──────────────────────────────────────────┤                    │
│ 学生列表：分页、选中本页、状态显示        │ 可移除、清空         │
├──────────────────────────────────────────┴────────────────────┤
│ 上一页 / 页码 / 下一页                         取消 / 确认选择 │
└───────────────────────────────────────────────────────────────┘
```

## 数据接口

```http
GET /api/v1/users/?role_code=student&page=1&page_size=20&keyword=&grade=&major=&status=
```

新增筛选参数：

| 参数 | 说明 |
|---|---|
| `keyword` | 匹配姓名、账号、邮箱、手机号、学号、年级、专业、研究方向 |
| `grade` | 年级模糊筛选 |
| `major` | 专业模糊筛选 |
| `status` | 用户状态筛选 |

非管理员教师仍只能看到自己可访问的学生，权限边界由后端 `AccessControlService.accessible_student_ids` 保持。

## 组件合同

```vue
<StudentPickerDialog
  v-model:visible="visible"
  v-model="selectedStudentIds"
  title="选择学生"
  @confirm="handleConfirm"
/>
```

| 属性/事件 | 说明 |
|---|---|
| `visible` | 控制弹窗显示 |
| `modelValue` | 已选学生 ID 列表 |
| `title` | 弹窗标题 |
| `confirm` | 返回当前已知的已选学生对象 |

## 开源协议边界

该组件为项目内自研实现，仅使用本项目已有依赖 `Vue 3`、`Element Plus`、`Tailwind CSS`、`lucide-vue-next`。未复制第三方组件站源码或样式文件，因此不引入额外组件协议义务。

如果后续引入第三方开源组件，必须在合并前确认：

- 许可证是否允许商用和二次分发。
- 是否要求保留版权声明或 NOTICE。
- 是否与 Apache-2.0 兼容。
- README 或 `THIRD_PARTY_NOTICES` 是否需要补充归属信息。
