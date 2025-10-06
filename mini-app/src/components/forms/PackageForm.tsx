import React, { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Modal, Form, Input, Select } from 'antd';
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
      form.setFieldsValue(initialValues);
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
          rules={[{ required: true, message: 'Please enter the package title!' }]}
        >
          <Input />
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
        <Form.Item name="notes" label="Notes">
          <Input.TextArea rows={3} />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default PackageForm;
