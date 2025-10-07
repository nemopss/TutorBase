import React, { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Modal, Form, Input, Select, DatePicker } from 'antd';
import dayjs from 'dayjs';
import api from '../../services/api';

// --- Types --- //
interface Learner {
  id: number;
  display_name: string;
}

interface LearnerListResponse {
  items: Learner[];
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

// --- Component --- //
const PackageForm: React.FC<PackageFormProps> = ({ open, onCancel, onFinish, isLoading, initialValues }) => {
  const [form] = Form.useForm();

  const { data: learnersData, isLoading: isLoadingLearners } = useQuery<LearnerListResponse, Error>({
    queryKey: ['learners'],
    queryFn: fetchLearners,
  });

  useEffect(() => {
    if (initialValues) {
      form.setFieldsValue({
        ...initialValues,
        start_date: initialValues.start_date ? dayjs(initialValues.start_date) : null,
        end_date: initialValues.end_date ? dayjs(initialValues.end_date) : null,
      });
    } else {
      form.resetFields();
    }
  }, [initialValues, form, open]);

  const isEditing = !!initialValues;

  return (
    <Modal
      open={open}
      title={isEditing ? "Edit Package" : "Create New Package"}
      okText={isEditing ? "Save" : "Create"}
      cancelText="Cancel"
      onCancel={onCancel}
      onOk={() => {
        form
          .validateFields()
          .then((values) => {
            if (!isEditing) form.resetFields();
            onFinish(values);
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

        <Form.Item name="start_date" label="Start Date">
          <DatePicker style={{ width: '100%' }} format="YYYY-MM-DD" />
        </Form.Item>

        <Form.Item name="end_date" label="End Date">
          <DatePicker style={{ width: '100%' }} format="YYYY-MM-DD" />
        </Form.Item>

        <Form.Item 
          name="timezone" 
          label="Timezone"
          initialValue="Europe/Moscow"
        >
          <Select
            showSearch
            options={[
              { value: 'Europe/Moscow', label: 'Moscow (UTC+3)' },
              { value: 'Europe/London', label: 'London (UTC+0)' },
              { value: 'America/New_York', label: 'New York (UTC-5)' },
              { value: 'America/Los_Angeles', label: 'Los Angeles (UTC-8)' },
              { value: 'Asia/Tokyo', label: 'Tokyo (UTC+9)' },
              { value: 'Asia/Dubai', label: 'Dubai (UTC+4)' },
            ]}
          />
        </Form.Item>

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
