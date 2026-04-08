<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { Button, Loading, Toast, Avatar } from '$lib/components/ui';
	import { authStore } from '$lib/stores';
	import { apiClient } from '$lib/api/client';
	import { fade, fly, scale } from 'svelte/transition';
	import { elasticOut } from 'svelte/easing';
	import type { User } from '$lib/types';
	import { formatDateTime, isImageFile, isFileSizeValid, getMaxFileSize } from '$lib/utils';

	let loading = $state(true);
	let editMode = $state(false);
	let uploading = $state(false);
	let profile: User | null = $state(null);
	let error = $state('');
	let successMessage = $state('');

	// 編輯表單資料
	let editForm = $state({
		full_name: '',
		email: ''
	});

	// 修改密碼表單
	let passwordForm = $state({
		currentPassword: '',
		newPassword: '',
		confirmPassword: ''
	});
	let changingPassword = $state(false);

	// 響應式表單驗證
	let formErrors = $derived({
		full_name: validateFullName(editForm.full_name),
		email: validateEmail(editForm.email)
	});

	// 密碼表單驗證
	let passwordErrors = $derived({
		newPassword: validatePassword(passwordForm.newPassword),
		confirmPassword: validateConfirmPassword(passwordForm.newPassword, passwordForm.confirmPassword)
	});

	// 響應式檢查表單是否有效
	let isFormValid = $derived(!formErrors.full_name && !formErrors.email && editForm.email.trim());

	// 響應式檢查是否有變更
	let hasChanges = $derived.by(() => {
		if (profile === null) return false;
		return editForm.full_name !== (profile.full_name || '') ||
			editForm.email !== (profile.email ?? '');
	});

	// 密碼表單���否可提交
	let isPasswordFormValid = $derived(
		passwordForm.currentPassword.trim() !== '' &&
		passwordForm.newPassword.trim() !== '' &&
		passwordForm.confirmPassword.trim() !== '' &&
		!passwordErrors.newPassword &&
		!passwordErrors.confirmPassword
	);

	// 頭像上傳狀態
	let avatarUrl = $state('');

	// 頭像上傳
	let fileInput: HTMLInputElement = $state(null!);

	// 表單驗證函數
	function validateFullName(fullName: string): string {
		if (fullName.trim() && fullName.trim().length < 2) {
			return '姓名至少需要 2 個字符';
		}
		if (fullName.trim().length > 50) {
			return '姓名不能超過 50 個字符';
		}
		return '';
	}

	function validateEmail(email: string): string {
		if (!email.trim()) {
			return '請輸入電子郵件';
		}
		const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
		if (!emailRegex.test(email)) {
			return '請輸入有效的電子郵件格式';
		}
		return '';
	}

	function validatePassword(password: string): string {
		if (password && password.length < 6) {
			return '密碼至少需要 6 個字符';
		}
		if (password && password.length > 100) {
			return '密碼不能超過 100 個字符';
		}
		return '';
	}

	function validateConfirmPassword(password: string, confirmPassword: string): string {
		if (password && confirmPassword && password !== confirmPassword) {
			return '密碼與確認密碼不符';
		}
		return '';
	}

	onMount(async () => {
		await loadProfile();
	});

	async function loadProfile() {
		try {
			loading = true;
			error = '';
			
			const response = await apiClient.auth.getProfile();
			if (response) {
				profile = response;
				// 初始化編輯表單
				editForm.full_name = profile.full_name || '';
				editForm.email = profile.email ?? '';
			}
		} catch (err) {
			error = '載入個人資料失敗';
			console.error('載入個人資料錯誤:', err);
		} finally {
			loading = false;
		}
	}

	function toggleEditMode() {
		editMode = !editMode;
		if (!editMode && profile) {
			editForm.full_name = profile.full_name || '';
			editForm.email = profile.email ?? '';
		}
	}

	async function handleSubmit() {
		error = '';
		successMessage = '';

		// 使用響應式驗證結果
		if (!isFormValid) {
			error = '請修正表單中的錯誤';
			return;
		}

		try {
			loading = true;

			const updateData: any = {
				email: editForm.email,
				full_name: editForm.full_name || undefined
			};

			const response = await apiClient.auth.updateProfile(updateData);
			
			if (response) {
				profile = response;
				successMessage = '個人資料更新成功';
				editMode = false;
				// 更新 auth store 中的用戶資料
				authStore.updateUser(response);
			}
		} catch (err: any) {
			error = err.response?.data?.detail ?? err.response?.data?.error?.message ?? '更新失敗';
		} finally {
			loading = false;
		}
	}

	async function handleChangePassword() {
		error = '';
		successMessage = '';

		if (!isPasswordFormValid) {
			error = '請修正密碼表單中的錯誤';
			return;
		}

		try {
			changingPassword = true;
			await apiClient.auth.changePassword({
				current_password: passwordForm.currentPassword,
				new_password: passwordForm.newPassword
			});
			successMessage = '密碼修改成功';
			passwordForm.currentPassword = '';
			passwordForm.newPassword = '';
			passwordForm.confirmPassword = '';
		} catch (err: any) {
			error = err.response?.data?.detail ?? err.response?.data?.error?.message ?? '密碼修改失敗';
		} finally {
			changingPassword = false;
		}
	}

	async function handleAvatarUpload(event: Event) {
		const target = event.target as HTMLInputElement;
		const file = target.files?.[0];
		
		if (!file) {
			return;
		}

		// 檢查檔案類型 - 對於頭像仍然限制為圖片
		if (!isImageFile(file)) {
			error = '請選擇圖片檔案';
			return;
		}

		// 檢查檔案大小
		const maxSize = getMaxFileSize(file);
		if (!isFileSizeValid(file)) {
			error = `圖片大小不能超過 ${maxSize}MB`;
			return;
		}

		try {
			uploading = true;
			error = '';
			
			// 上傳圖片
			const uploadResponse = await apiClient.files.uploadImage(file);
			if (uploadResponse.url) {
				// 更新用戶頭像
				const updateResponse = await apiClient.auth.updateProfile({
					avatar: uploadResponse.url
				});
				
				if (updateResponse) {
					profile = updateResponse;
					avatarUrl = updateResponse.avatar ?? ''; // 更新頭像 URL
					successMessage = '頭像更新成功';
					// 更新 auth store
					authStore.updateUser(updateResponse);
				}
			}
		} catch (err: any) {
			error = err.response?.data?.detail ?? err.response?.data?.error?.message ?? '頭像上傳失敗';
		} finally {
			uploading = false;
			// 清空檔案選擇
			if (fileInput) {
				fileInput.value = '';
			}
		}
	}

	function triggerFileUpload() {
		fileInput?.click();
	}
</script>

<div class="max-w-4xl mx-auto p-4">
	<div class="card bg-base-100 shadow-xl">
		<div class="card-body">
			<div class="flex justify-between items-center mb-6">
				<h1 class="text-2xl font-bold">個人資料</h1>
				{#if !loading && profile}
					<Button 
						variant={editMode ? 'ghost' : 'primary'}
						size="sm"
						onclick={toggleEditMode}
					>
						{editMode ? '取消編輯' : '編輯資料'}
					</Button>
				{/if}
			</div>

			{#if loading}
				<div class="flex justify-center py-8">
					<Loading size="lg" />
				</div>
			{:else if profile}
				<div class="grid md:grid-cols-3 gap-6">
					<!-- 左側：頭像區域 -->
					<div class="md:col-span-1">
						<div class="flex flex-col items-center space-y-4">
							<div 
								class="relative inline-block ring-4 ring-base-300 rounded-full transition-all duration-300 {uploading ? 'ring-primary animate-pulse' : ''}"
								in:scale={{ duration: 300, easing: elasticOut }}
							>
								<Avatar
									user={{ username: profile.username, avatar: avatarUrl || profile?.avatar || '' }}
									size="xl"
									alt={profile.username ?? ''}
								/>
								{#if editMode}
									<button
										type="button"
										class="absolute bottom-0 right-0 btn btn-circle btn-sm btn-primary transition-all duration-200 hover:scale-110"
										onclick={triggerFileUpload}
										disabled={uploading}
										in:scale={{ duration: 300, delay: 200 }}
									>
										{#if uploading}
											<span class="loading loading-spinner loading-xs"></span>
										{:else}
											<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
											</svg>
										{/if}
									</button>
								{/if}
							</div>
							<input
								bind:this={fileInput}
								type="file"
								accept="image/*"
								class="hidden"
								onchange={handleAvatarUpload}
							/>
							<div class="text-center">
								<h2 class="text-xl font-semibold">{profile.username}</h2>
								<p class="text-sm text-base-content/60">@{profile.username}</p>
							</div>
						</div>
					</div>

					<!-- 右側：資料表單 -->
					<div class="md:col-span-2">
						{#if editMode}
							<!-- 編輯模式 -->
							<form 
								onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} 
								class="space-y-4"
								in:fade={{ duration: 300 }}
							>
								<div class="form-control">
									<label class="label" for="username">
										<span class="label-text">用戶名稱</span>
									</label>
									<input
										id="username"
										type="text"
										value={profile.username}
										class="input input-bordered"
										disabled
									/>
									<div class="label">
										<span class="label-text-alt text-base-content/60">用戶名稱無法修改</span>
									</div>
								</div>

								<div class="form-control">
									<label class="label" for="full_name">
										<span class="label-text">姓名</span>
									</label>
									<input
										id="full_name"
										type="text"
										bind:value={editForm.full_name}
										class="input input-bordered transition-colors duration-200"
										class:input-error={formErrors.full_name}
										class:input-success={editForm.full_name && !formErrors.full_name}
										placeholder="請輸入您的姓名"
									/>
									<!-- use:autofocus={editMode} -->
									{#if formErrors.full_name}
										<div class="label" in:fly={{ y: -10, duration: 200 }}>
											<span class="label-text-alt text-error">{formErrors.full_name}</span>
										</div>
									{/if}
								</div>

								<div class="form-control">
									<label class="label" for="email">
										<span class="label-text">電子郵件 *</span>
									</label>
									<input
										id="email"
										type="email"
										bind:value={editForm.email}
										class="input input-bordered transition-colors duration-200"
										class:input-error={formErrors.email}
										class:input-success={editForm.email && !formErrors.email}
										required
									/>
									{#if formErrors.email}
										<div class="label" in:fly={{ y: -10, duration: 200 }}>
											<span class="label-text-alt text-error">{formErrors.email}</span>
										</div>
									{/if}
								</div>

								<div class="mt-6 flex justify-between items-center">
									<!-- 變更指示器 -->
									{#if hasChanges}
										<div 
											class="text-sm text-warning flex items-center space-x-2"
											in:fly={{ x: -20, duration: 200 }}
										>
											<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
											</svg>
											<span>您有未保存的變更</span>
										</div>
									{:else}
										<div></div>
									{/if}

									<!-- 操作按鈕 -->
									<div class="flex space-x-2">
										<Button
											variant="outline"
											onclick={toggleEditMode}
											disabled={loading}
										>
											取消
										</Button>
										<Button
											variant="primary"
											type="submit"
											disabled={loading || !isFormValid || !hasChanges}
										>
											{#if loading}
												<span class="loading loading-spinner loading-sm"></span>
											{/if}
											儲存變更
										</Button>
									</div>
								</div>
							</form>

							<!-- 修改密碼區塊 -->
							<div class="divider mt-8">修改密碼</div>
							<form
								onsubmit={(e) => { e.preventDefault(); handleChangePassword(); }}
								class="space-y-4"
							>
								<div class="form-control">
									<label class="label" for="currentPassword">
										<span class="label-text">目前密碼 *</span>
									</label>
									<input
										id="currentPassword"
										type="password"
										bind:value={passwordForm.currentPassword}
										class="input input-bordered transition-colors duration-200"
										placeholder="請輸入目前的密碼"
										required
									/>
								</div>

								<div class="form-control">
									<label class="label" for="newPassword">
										<span class="label-text">新密碼 *</span>
									</label>
									<input
										id="newPassword"
										type="password"
										bind:value={passwordForm.newPassword}
										class="input input-bordered transition-colors duration-200"
										class:input-error={passwordErrors.newPassword}
										class:input-success={passwordForm.newPassword && !passwordErrors.newPassword}
										placeholder="請輸入新密碼（至少 6 個字符）"
										required
									/>
									{#if passwordErrors.newPassword}
										<div class="label" in:fly={{ y: -10, duration: 200 }}>
											<span class="label-text-alt text-error">{passwordErrors.newPassword}</span>
										</div>
									{/if}
								</div>

								<div class="form-control">
									<label class="label" for="confirmNewPassword">
										<span class="label-text">確認新密碼 *</span>
									</label>
									<input
										id="confirmNewPassword"
										type="password"
										bind:value={passwordForm.confirmPassword}
										class="input input-bordered transition-colors duration-200"
										class:input-error={passwordErrors.confirmPassword}
										class:input-success={passwordForm.confirmPassword && !passwordErrors.confirmPassword}
										placeholder="請再次輸入新密碼"
										required
									/>
									{#if passwordErrors.confirmPassword}
										<div class="label" in:fly={{ y: -10, duration: 200 }}>
											<span class="label-text-alt text-error">{passwordErrors.confirmPassword}</span>
										</div>
									{/if}
								</div>

								<div class="flex justify-end">
									<Button
										variant="primary"
										type="submit"
										disabled={changingPassword || !isPasswordFormValid}
									>
										{#if changingPassword}
											<span class="loading loading-spinner loading-sm"></span>
										{/if}
										修改密碼
									</Button>
								</div>
							</form>
						{:else}
							<!-- 查看模式 -->
							<div class="space-y-4">
								<div>
									<div class="label">
										<span class="label-text text-base-content/60">用戶名稱</span>
									</div>
									<p class="text-lg">{profile.username}</p>
								</div>

								<div>
									<div class="label">
										<span class="label-text text-base-content/60">姓名</span>
									</div>
									<p class="text-lg">{profile.full_name || '未設定'}</p>
								</div>

								<div>
									<div class="label">
										<span class="label-text text-base-content/60">電子郵件</span>
									</div>
									<p class="text-lg">{profile.email}</p>
								</div>

								<div>
									<div class="label">
										<span class="label-text text-base-content/60">帳號狀態</span>
									</div>
									<div class="badge badge-success">
										{profile.is_active ? '啟用中' : '已停用'}
									</div>
								</div>

								<div>
									<div class="label">
										<span class="label-text text-base-content/60">註冊時間</span>
									</div>
									<p class="text-lg">{formatDateTime(profile.created_at ?? '')}</p>
								</div>
							</div>
						{/if}
					</div>
				</div>
			{:else}
				<div class="flex justify-center py-8">
					<div class="text-center">
						<p class="text-lg text-base-content/60 mb-4">無法載入個人資料</p>
						<button class="btn btn-primary" onclick={loadProfile}>重新載入</button>
					</div>
				</div>
			{/if}

			{#if error}
				<div class="alert alert-error mt-4">
					<svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
					</svg>
					<span>{error}</span>
				</div>
			{/if}

			{#if successMessage}
				<div class="alert alert-success mt-4">
					<svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
					</svg>
					<span>{successMessage}</span>
				</div>
			{/if}
		</div>
	</div>
</div>

<style>
	@reference "$lib/styles/tailwind.css";

	/* 表單驗證樣式增強 */
	.input-error {
		@apply border-error focus:border-error;
		box-shadow: 0 0 0 1px rgba(var(--er), 0.2);
	}

	.input-success {
		@apply border-success focus:border-success;
		box-shadow: 0 0 0 1px rgba(var(--su), 0.2);
	}

	/* 頭像上傳按鈕動畫 */
	.btn-circle:hover {
		transform: scale(1.1);
	}

	/* 表單動畫 */
	.form-control {
		transition: all 0.2s ease;
	}

	.form-control:focus-within {
		transform: translateY(-1px);
	}

	/* 自定義滾動條 */
	.max-w-4xl {
		scrollbar-width: thin;
		scrollbar-color: rgba(var(--p), 0.3) transparent;
	}

	.max-w-4xl::-webkit-scrollbar {
		width: 6px;
	}

	.max-w-4xl::-webkit-scrollbar-track {
		background: transparent;
	}

	.max-w-4xl::-webkit-scrollbar-thumb {
		background: rgba(var(--p), 0.3);
		border-radius: 3px;
	}

	.max-w-4xl::-webkit-scrollbar-thumb:hover {
		background: rgba(var(--p), 0.5);
	}
</style>