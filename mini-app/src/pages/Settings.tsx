import React, { useState } from 'react';
import { Card, Form, Input, Select, Switch, Button, message, Divider, Avatar, Space, Typography } from 'antd';
import { UserOutlined, BellOutlined, GlobalOutlined, BgColorsOutlined } from '@ant-design/icons';
import { useAuth } from '../auth/AuthProvider';
import PageHeader from '../components/common/PageHeader';
import { useThemeMode } from '../theme/ThemeProvider';
import type { ThemeMode } from '../theme/ThemeProvider';

const { Title, Text } = Typography;

const TIMEZONE_OPTIONS = [
  { value: 'Europe/Moscow', label: 'Moscow (UTC+3)' },
  { value: 'Europe/London', label: 'London (UTC+0)' },
  { value: 'America/New_York', label: 'New York (UTC-5)' },
  { value: 'America/Los_Angeles', label: 'Los Angeles (UTC-8)' },
  { value: 'Asia/Tokyo', label: 'Tokyo (UTC+9)' },
  { value: 'Asia/Dubai', label: 'Dubai (UTC+4)' },
];

const Settings: React.FC = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();
  const { mode, setMode } = useThemeMode();

  const handleSave = async (values: any) => {
    setLoading(true);
    try {
      // TODO: Implement API call to save settings
      await new Promise(resolve => setTimeout(resolve, 1000)); // Simulate API call
      message.success('Settings saved successfully!');
      if (import.meta.env.DEV) {
        console.log('Settings:', values);
      }
    } catch (error: any) {
      message.error(`Failed to save settings: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <PageHeader 
        title="Settings"
        subtitle="Manage your profile and preferences"
      />
      
      {/* Profile Section */}
      <Card 
        title={
          <Space>
            <UserOutlined />
            <span>Profile</span>
          </Space>
        }
        style={{ marginBottom: 24 }}
      >
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <Avatar size={64} icon={<UserOutlined />} />
            <div>
              <Title level={4} style={{ margin: 0 }}>{user?.display_name || 'User'}</Title>
              <Text type="secondary">Role: {user?.role || 'viewer'}</Text>
            </div>
          </div>
          <Form layout="vertical">
            <Form.Item label="Display Name" initialValue={user?.display_name}>
              <Input placeholder="Your display name" disabled />
            </Form.Item>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Profile information is synced from your Telegram account
            </Text>
          </Form>
        </Space>
      </Card>

      {/* Preferences Section */}
      <Card 
        title={
          <Space>
            <GlobalOutlined />
            <span>Preferences</span>
          </Space>
        }
        style={{ marginBottom: 24 }}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSave}
          initialValues={{
            timezone: 'Europe/Moscow',
            notifications_enabled: true,
            email_notifications: false,
            lesson_reminders: true,
            package_updates: true,
          }}
        >
          <Form.Item
            name="timezone"
            label="Default Timezone"
            help="Used for displaying dates and scheduling lessons"
          >
            <Select options={TIMEZONE_OPTIONS} />
          </Form.Item>

          <Divider />

          <Title level={5}>
            <BellOutlined /> Notifications
          </Title>

          <Form.Item
            name="notifications_enabled"
            label="Enable Notifications"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>

          <Form.Item
            name="lesson_reminders"
            label="Lesson Reminders"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>

          <Form.Item
            name="package_updates"
            label="Package Updates"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>

          <Form.Item
            name="email_notifications"
            label="Email Notifications"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>

          <Divider />

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              Save Preferences
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {/* Appearance Section */}
      <Card 
        title={
          <Space>
            <BgColorsOutlined />
            <span>Appearance</span>
          </Space>
        }
      >
        <Form layout="vertical">
          <Form.Item label="Theme" help="Choose how the interface should look in the mini-app">
            <Select
              value={mode}
              onChange={(value: ThemeMode) => setMode(value)}
              options={[
                { value: 'auto', label: 'Auto (follow Telegram)' },
                { value: 'light', label: 'Light' },
                { value: 'dark', label: 'Dark' },
              ]}
            />
          </Form.Item>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Switch to «Auto» to sync with Telegram again. The change applies immediately.
          </Text>
        </Form>
      </Card>
    </div>
  );
};

export default Settings;
