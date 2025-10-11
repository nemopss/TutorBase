import React, { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Modal, Form, Input, Select, DatePicker } from 'antd';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import api from '../../services/api';

dayjs.extend(utc);

// --- Types --- //
interface Learner {
  id: number;
  display_name: string;
}

interface LearnerListResponse {
  items: Learner[];
}

interface Template {
  id: number;
  name: string;
  description?: string;
  timezone: string;
}

interface TemplateListResponse {
  total: number;
  items: Template[];
}

interface PackageFormProps {
  open: boolean;
  onCancel: () => void;
  onFinish: (values: any) => void;
  isLoading: boolean;
  initialValues?: any;
}

// --- API Fetcher --- //
const fetchLearners = async (): Promise<LearnerListResponse> => {
  const { data } = await api.get('/learners');
  return data;
};

const fetchTemplates = async (): Promise<TemplateListResponse> => {
  const { data } = await api.get('/templates');
  return data;
};

// --- Component --- //
const PackageForm: React.FC<PackageFormProps> = ({ open, onCancel, onFinish, isLoading, initialValues }) => {
  const [form] = Form.useForm();

  const { data: learnersData, isLoading: isLoadingLearners } = useQuery<LearnerListResponse, Error>({
    queryKey: ['learners'],
    queryFn: fetchLearners,
  });

  const { data: templatesData, isLoading: isLoadingTemplates } = useQuery<TemplateListResponse, Error>({
    queryKey: ['templates'],
    queryFn: fetchTemplates,
  });

  useEffect(() => {
    if (!open) {
      return;
    }

    if (initialValues) {
      form.setFieldsValue({
        ...initialValues,
        start_date: initialValues.start_date ? dayjs(initialValues.start_date) : null,
        end_date: initialValues.end_date ? dayjs(initialValues.end_date) : null,
        learner_id: initialValues.learner_id ?? initialValues.learner?.id,
      });
    } else {
      form.resetFields();
    }
  }, [initialValues, form, open]);

  const isEditing = !!initialValues;
  const selectedTemplateId = Form.useWatch('template_id', form);
  const shouldRequireStartDate = !isEditing && !!selectedTemplateId;

  return (
    <Modal
      open={open}
      title={isEditing ? `Edit Package${initialValues?.title ? `: ${initialValues.title}` : ''}` : "Create New Package"}
      okText={isEditing ? "Save" : "Create"}
      cancelText="Cancel"
      onCancel={onCancel}
      onOk={() => {
        form
          .validateFields()
          .then((values) => {
            const selectedTemplate = templatesData?.items.find(template => template.id === values.template_id);
            const resolvedTimezone = values.timezone ?? selectedTemplate?.timezone ?? 'Europe/Moscow';

            const startDateValue = values.start_date;
            const endDateValue = values.end_date;
            const totalLessonsRaw = values.total_lessons;
            const totalLessons =
              totalLessonsRaw === undefined || totalLessonsRaw === null || totalLessonsRaw === ''
                ? undefined
                : Number(totalLessonsRaw);

            const formattedValues: any = {
              ...values,
              timezone: resolvedTimezone,
            };

            // Обрабатываем даты правильно
            if (startDateValue) {
              if (isEditing) {
                // При редактировании отправляем только если дата изменилась
                const originalDate = initialValues?.start_date ? dayjs(initialValues.start_date).format('YYYY-MM-DD') : null;
                const newDate = startDateValue.format('YYYY-MM-DD');
                if (originalDate !== newDate) {
                  // Отправляем начало дня в UTC
                  formattedValues.start_date = startDateValue.startOf('day').utc().toISOString();
                } else {
                  delete formattedValues.start_date;
                }
              } else {
                // Для создания с шаблоном - отправляем дату в формате YYYY-MM-DD
                formattedValues.start_date = startDateValue.format('YYYY-MM-DD');
              }
            } else {
              delete formattedValues.start_date;
            }
            
            if (endDateValue) {
              if (isEditing) {
                // При редактировании отправляем только если дата изменилась
                const originalDate = initialValues?.end_date ? dayjs(initialValues.end_date).format('YYYY-MM-DD') : null;
                const newDate = endDateValue.format('YYYY-MM-DD');
                if (originalDate !== newDate) {
                  // Отправляем конец дня в UTC
                  formattedValues.end_date = endDateValue.endOf('day').utc().toISOString();
                } else {
                  delete formattedValues.end_date;
                }
              } else {
                formattedValues.end_date = endDateValue.endOf('day').utc().toISOString();
              }
            } else {
              delete formattedValues.end_date;
            }
            
            if (totalLessons !== undefined) {
              formattedValues.total_lessons = totalLessons;
            }

            // Удаляем поля которые не нужно отправлять
            if (!isEditing) {
              // При создании удаляем template_id если не выбран
              if (!formattedValues.template_id) {
                delete formattedValues.template_id;
              }
            } else {
              // При редактировании удаляем learner_id и template_id (они не должны меняться)
              delete formattedValues.learner_id;
              delete formattedValues.template_id;
            }

            if (!isEditing) form.resetFields();
            onFinish(formattedValues);
          })
          .catch((info) => {
            console.log('Validate Failed:', info);
          });
      }}
      confirmLoading={isLoading}
      destroyOnClose
    >
      <Form form={form} layout="vertical" name="package_form">
        <Form.Item
          name="title"
          label="Package Title"
          rules={[{ required: !isEditing, message: 'Please enter the package title!' }]}
        >
          <Input placeholder="e.g., English Course - Spring 2024" />
        </Form.Item>
        
        {!isEditing && (
          <>
            <Form.Item
              name="template_id"
              label="Template (optional)"
            >
              <Select
                allowClear
                showSearch
                placeholder="Select a template to pre-fill lessons"
                loading={isLoadingTemplates}
                optionFilterProp="label"
                filterOption={(input, option) => String(option?.label ?? '').toLowerCase().includes(input.toLowerCase())}
                options={templatesData?.items.map(template => ({
                  value: template.id,
                  label: template.name,
                }))}
              />
            </Form.Item>
            
            <Form.Item
              name="learner_id"
              label="Learner"
              rules={[{ required: true, message: 'Please select a learner!' }]}
            >
              <Select
                showSearch
                placeholder="Select a learner"
                loading={isLoadingLearners}
                optionFilterProp="children"
                filterOption={(input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())}
                options={learnersData?.items.map(learner => ({ value: learner.id, label: learner.display_name }))}
              />
            </Form.Item>
          </>
        )}

        <Form.Item
          name="status"
          label="Status"
          initialValue="draft"
        >
          <Select
            options={[
              { value: 'draft', label: 'Draft' },
              { value: 'active', label: 'Active' },
              { value: 'completed', label: 'Completed' },
              { value: 'archived', label: 'Archived' },
            ]}
          />
        </Form.Item>

        <Form.Item
          name="start_date"
          label="Start Date"
          rules={shouldRequireStartDate ? [{ required: true, message: 'Start date is required when using a template.' }] : []}
        >
          <DatePicker 
            style={{ width: '100%' }} 
            format="YYYY-MM-DD"
            showTime={false}
          />
        </Form.Item>

        {/* <Form.Item name="end_date" label="End Date">
          <DatePicker style={{ width: '100%' }} format="YYYY-MM-DD" />
        </Form.Item>
        */}

        {/* timezone removed from the form UI; resolved from template or defaulted on submit */}

       

        <Form.Item name="total_lessons" label="Total Lessons (optional)">
          <Input type="number" min={1} placeholder="e.g., 20" />
        </Form.Item>

        <Form.Item name="notes" label="Notes">
          <Input.TextArea rows={3} placeholder="Additional notes about this package..." />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default PackageForm;
