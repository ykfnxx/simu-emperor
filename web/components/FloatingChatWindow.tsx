'use client';

import { createPortal } from 'react-dom';
import { useModalDialogFocus } from './useModalDialogFocus';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import type {
  CharacterId,
  CharacterPublicView,
  GameplayConversation,
  GameplayCourtView,
  GameplayMessage,
  OfficeId,
  OfficeView
} from '../../src/contracts/gameplay';
import {
  getAppointedCharacters,
  getCharacterPortraitClass,
  getConversationCharacterIds
} from '../client-api';

export interface FloatingChatWindowProps {
  open: boolean;
  courtView: GameplayCourtView;
  characterById: ReadonlyMap<CharacterId, CharacterPublicView>;
  conversations: GameplayConversation[];
  activeConversationId: string | null;
  selectedContactCharacterId: CharacterId | null;
  activeMessages: GameplayMessage[];
  messagesLoading: boolean;
  chatBusy: boolean;
  chatError: string | null;
  isHistoryView: boolean;
  draftText: string;
  groupMentions: CharacterId[];
  onClose: () => void;
  onSelectCharacterContact: (characterId: CharacterId) => void;
  onSelectConversation: (conversationId: string) => void;
  onRefreshConversation: () => void;
  onChangeDraft: (text: string) => void;
  onToggleGroupMention: (characterId: CharacterId) => void;
  onSendMessage: () => void;
  onCreateGroupConversation: (
    title: string,
    characterIds: CharacterId[]
  ) => Promise<void> | void;
  onOpenBiography?: (
    characterId: CharacterId,
    anchorEl?: HTMLElement | null
  ) => void;
  onHoverBiography?: (
    characterId: CharacterId,
    anchorEl?: HTMLElement | null
  ) => void;
  onLeaveBiography?: (anchorEl?: HTMLElement) => void;
  biographyOpen: boolean;
}

export const FloatingChatWindow: React.FC<FloatingChatWindowProps> = ({
  open,
  courtView,
  characterById,
  conversations,
  activeConversationId,
  selectedContactCharacterId,
  activeMessages,
  messagesLoading,
  chatBusy,
  chatError,
  isHistoryView,
  draftText,
  groupMentions,
  onClose,
  onSelectCharacterContact,
  onSelectConversation,
  onRefreshConversation,
  onChangeDraft,
  onToggleGroupMention,
  onSendMessage,
  onCreateGroupConversation,
  onOpenBiography,
  onHoverBiography,
  onLeaveBiography,
  biographyOpen
}) => {
  const [membersPopupOpen, setMembersPopupOpen] = useState(false);
  const [groupCreateOpen, setGroupCreateOpen] = useState(false);
  const [groupTitle, setGroupTitle] = useState('三省钱粮会商');
  const [selectedGroupMemberIds, setSelectedGroupMemberIds] = useState<CharacterId[]>([]);

  const messagesContainerRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const membersDialogRef = useRef<HTMLElement | null>(null);
  const groupCreateDialogRef = useRef<HTMLElement | null>(null);

  useModalDialogFocus(membersPopupOpen, membersDialogRef);
  useModalDialogFocus(groupCreateOpen, groupCreateDialogRef);

  useEffect(() => {
    if (!open) {
      setMembersPopupOpen(false);
      setGroupCreateOpen(false);
    }
  }, [open]);

  useEffect(() => {
    if (!membersPopupOpen && !groupCreateOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !biographyOpen) {
        e.stopPropagation();
        e.preventDefault();
        if (membersPopupOpen) {
          setMembersPopupOpen(false);
        } else if (groupCreateOpen) {
          setGroupCreateOpen(false);
        }
      }
    };
    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [membersPopupOpen, groupCreateOpen, biographyOpen]);

  const canInteract =
    !isHistoryView && courtView.active_turn.phase !== 'ARCHIVED';

  const activeOfficeByCharacter = useMemo(() => {
    const officeById = new Map<OfficeId, OfficeView>(
      courtView.offices.map((o) => [o.office_id, o])
    );
    const map = new Map<CharacterId, OfficeView>();
    for (const pv of courtView.provinces) {
      const appt = pv.appointment;
      if (appt) {
        const off = officeById.get(appt.office_id);
        if (off) {
          map.set(appt.character_id, off);
        }
      }
    }
    return map;
  }, [courtView.provinces, courtView.offices]);

  const appointedCharacters = useMemo(
    () => getAppointedCharacters(courtView),
    [courtView]
  );

  useEffect(() => {
    if (groupCreateOpen) {
      setSelectedGroupMemberIds(appointedCharacters.map((c) => c.character_id));
    }
  }, [groupCreateOpen, appointedCharacters]);

  const activeConversation = useMemo(
    () =>
      conversations.find((c) => c.conversation_id === activeConversationId) ??
      null,
    [conversations, activeConversationId]
  );

  const activeCharIds = useMemo(
    () =>
      activeConversation ? getConversationCharacterIds(activeConversation) : [],
    [activeConversation]
  );

  const headerCharacter = useMemo(() => {
    if (activeConversation?.kind === 'dm' && activeCharIds[0]) {
      return characterById.get(activeCharIds[0]) ?? null;
    }
    if (!activeConversation && selectedContactCharacterId) {
      return characterById.get(selectedContactCharacterId) ?? null;
    }
    return null;
  }, [
    activeConversation,
    activeCharIds,
    selectedContactCharacterId,
    characterById
  ]);

  const headerOfficeTitle = useMemo(() => {
    if (!headerCharacter) return '';
    return (
      activeOfficeByCharacter.get(headerCharacter.character_id)?.title ?? '候任'
    );
  }, [headerCharacter, activeOfficeByCharacter]);

  const dmConversationByCharacter = useMemo(() => {
    const map = new Map<CharacterId, GameplayConversation>();
    for (const conv of conversations) {
      if (conv.kind === 'dm') {
        const charId = getConversationCharacterIds(conv)[0];
        if (charId && !map.has(charId)) {
          map.set(charId, conv);
        }
      }
    }
    return map;
  }, [conversations]);

  const groupConversations = useMemo(
    () => conversations.filter((c) => c.kind === 'group'),
    [conversations]
  );

  useEffect(() => {
    if (!open) return;
    const el = messagesContainerRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [open, activeConversationId, activeMessages.length]);

  useEffect(() => {
    if (open && canInteract) {
      inputRef.current?.focus();
    }
  }, [open, activeConversationId, selectedContactCharacterId, canInteract]);

  useEffect(() => {
    if (open && canInteract && !chatBusy && document.activeElement === document.body) {
      inputRef.current?.focus();
    }
  }, [chatBusy, open, canInteract]);

  if (!open) {
    return null;
  }

  const canSendInCurrentView =
    canInteract &&
    (activeConversation !== null || selectedContactCharacterId !== null);

  const handleToggleNewGroupMember = (characterId: CharacterId) => {
    setSelectedGroupMemberIds((prev) =>
      prev.includes(characterId)
        ? prev.filter((id) => id !== characterId)
        : [...prev, characterId]
    );
  };

  const handleConfirmCreateGroup = async () => {
    if (!canInteract || selectedGroupMemberIds.length === 0) return;
    await onCreateGroupConversation(
      groupTitle.trim() || '三省廷议',
      selectedGroupMemberIds
    );
    setGroupCreateOpen(false);
  };

  const groupMemberSubtitle =
    activeConversation?.kind === 'group'
      ? activeCharIds
          .map((id) => characterById.get(id)?.name ?? id)
          .join('、')
      : '';

  return (
    <>
      <section
        className="panel chat-window"
        id="floating-chat"
        aria-label="御前密谈"
        data-testid="floating-chat-window"
      >
        <div className="chat-sidebar">
          <div className="sidebar-head">
            <h2>御前密谈</h2>
            <button
              type="button"
              className="button"
              id="new-group-chat"
              data-testid="new-group-chat-btn"
              title="新建廷议"
              aria-label="新建廷议"
              disabled={!canInteract}
              onClick={() => setGroupCreateOpen(true)}
            >
              <svg
                width="13"
                height="13"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.4"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
                style={{ verticalAlign: '-2px', marginRight: '3px' }}
              >
                <path d="M12 5v14" />
                <path d="M5 12h14" />
              </svg>
              新议
            </button>
          </div>
          <div className="contacts" id="chat-contacts">
            {groupConversations.map((groupConv) => {
              const isActive = activeConversationId === groupConv.conversation_id;
              const memberIds = getConversationCharacterIds(groupConv);
              const ringMembers = memberIds.slice(0, 4);
              const memberNames = memberIds
                .map((id) => characterById.get(id)?.name ?? id)
                .join('、');
              return (
                <button
                  key={groupConv.conversation_id}
                  type="button"
                  className={`contact ${isActive ? 'active' : ''}`}
                  data-chat-group={groupConv.conversation_id}
                  data-testid={`chat-group-${groupConv.conversation_id}`}
                  onClick={() => onSelectConversation(groupConv.conversation_id)}
                >
                  <span className="group-avatar" aria-hidden="true">
                    {ringMembers.map((mId) => (
                      <span
                        key={mId}
                        className={`mini-portrait ${getCharacterPortraitClass(mId)}`}
                      />
                    ))}
                  </span>
                  <span className="contact-meta">
                    <strong>{groupConv.title}</strong>
                    <small>{memberNames || `${memberIds.length}人廷议`}</small>
                  </span>
                </button>
              );
            })}

            {courtView.characters.map((char) => {
              const existingDm = dmConversationByCharacter.get(char.character_id);
              const isActive = existingDm
                ? activeConversationId === existingDm.conversation_id
                : !activeConversationId &&
                  selectedContactCharacterId === char.character_id;
              const officeTitle =
                activeOfficeByCharacter.get(char.character_id)?.title ?? '候任';
              return (
                <button
                  key={char.character_id}
                  type="button"
                  className={`contact ${isActive ? 'active' : ''}`}
                  data-chat-select={char.character_id}
                  data-testid={`chat-contact-${char.character_id}`}
                  onClick={() => {
                    if (existingDm) {
                      onSelectConversation(existingDm.conversation_id);
                    } else {
                      onSelectCharacterContact(char.character_id);
                    }
                  }}
                >
                  <span
                    className={`portrait ${getCharacterPortraitClass(char.character_id)}`}
                    aria-hidden="true"
                  />
                  <span className="contact-meta">
                    <strong>{char.name}</strong>
                    <small>{officeTitle}</small>
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="conversation">
          <div className="conversation-head">
            <div className="conversation-title-block">
              {activeConversation?.kind === 'group' ? (
                <>
                  <strong id="chat-person-name">{activeConversation.title}</strong>
                  <small id="chat-person-role" className="conversation-sub">
                    {groupMemberSubtitle}
                  </small>
                </>
              ) : headerCharacter ? (
                <>
                  <strong id="chat-person-name">{headerCharacter.name}</strong>
                  <small id="chat-person-role" className="conversation-sub">
                    {headerOfficeTitle}
                  </small>
                </>
              ) : (
                <>
                  <strong id="chat-person-name">御前密谈</strong>
                  <small id="chat-person-role" className="conversation-sub">
                    臣工奏对
                  </small>
                </>
              )}
            </div>

            <div className="conversation-actions">
              {activeConversation?.kind === 'group' && (
                <button
                  type="button"
                  className="chat-head-btn"
                  id="chat-members-btn"
                  data-testid="chat-members-btn"
                  title="廷议成员"
                  aria-label="廷议成员"
                  onClick={() => setMembersPopupOpen(true)}
                >
                  成员 ({activeCharIds.length})
                </button>
              )}
              <button
                type="button"
                className="chat-head-btn"
                id="chat-refresh-btn"
                data-testid="chat-refresh-btn"
                title="刷新会话"
                aria-label="刷新会话"
                disabled={!activeConversation || messagesLoading}
                onClick={onRefreshConversation}
              >
                刷新
              </button>
              <button
                type="button"
                className="icon-close"
                id="close-chat"
                data-testid="close-chat-btn"
                aria-label="关闭"
                onClick={onClose}
              >
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M18 6 6 18" />
                  <path d="m6 6 12 12" />
                </svg>
              </button>
            </div>
          </div>

          <div
            ref={messagesContainerRef}
            className="messages"
            id="chat-messages"
            data-testid="chat-messages-list"
          >
            {activeMessages.length === 0 ? (
              <div className="chat-empty-state">
                {messagesLoading
                  ? '调取会话记录...'
                  : !activeConversation
                    ? isHistoryView
                      ? '当轮无此臣工密谈记录'
                      : '输入圣谕即可开启密谈'
                    : '尚无往来奏对记录'}
              </div>
            ) : (
              activeMessages.map((msg) => {
                const isMonarch = msg.sender_id === 'monarch';
                const senderChar = !isMonarch
                  ? characterById.get(msg.sender_id as CharacterId)
                  : undefined;
                const senderName = isMonarch
                  ? '圣谕'
                  : (senderChar?.name ?? msg.sender_id);
                const senderRole = !isMonarch
                  ? (activeOfficeByCharacter.get(msg.sender_id as CharacterId)?.title ?? '')
                  : '';

                return (
                  <div
                    key={msg.seq}
                    className={`message ${isMonarch ? 'self' : 'agent'}`}
                    data-testid={`chat-msg-${msg.seq}`}
                  >
                    {!isMonarch && (
                      <div
                        className={`portrait ${getCharacterPortraitClass(msg.sender_id as CharacterId)}`}
                        aria-hidden="true"
                      />
                    )}
                    <div className="bubble">
                      <div className="sender">
                        <span>{senderName}</span>
                        {senderRole && <span>{senderRole}</span>}
                        <span>第{msg.source_turn}轮</span>
                        {msg.is_late && <em className="chat-late-badge">迟达</em>}
                        {msg.mentions.length > 0 && (
                          <em className="chat-mention-badge">
                            {msg.mentions
                              .map((id) => `@${characterById.get(id)?.name ?? id}`)
                              .join(' ')}
                          </em>
                        )}
                        {msg.wake_targets.length > 0 && (
                          <em className="chat-receipt-badge">
                            已传召{' '}
                            {msg.wake_targets
                              .map((id) => characterById.get(id)?.name ?? id)
                              .join(' ')}
                          </em>
                        )}
                      </div>
                      <p className="msg-text">{msg.content}</p>
                    </div>
                    {isMonarch && <div className="monarch-avatar" aria-hidden="true" />}
                  </div>
                );
              })
            )}
          </div>

          <div className="composer">
            {activeConversation?.kind === 'group' && canInteract && (
              <div className="mention-row" id="mention-row" data-testid="chat-mention-bar">
                {activeCharIds.map((charId) => {
                  const char = characterById.get(charId);
                  const checked = groupMentions.includes(charId);
                  return (
                    <button
                      key={charId}
                      type="button"
                      className={`mention-chip ${checked ? 'active' : ''}`}
                      data-testid={`mention-chip-${charId}`}
                      onClick={() => onToggleGroupMention(charId)}
                    >
                      @{char?.name ?? charId}
                    </button>
                  );
                })}
              </div>
            )}

            {chatError && (
              <div className="chat-error-strip" role="alert">
                {chatError}
              </div>
            )}

            <div className="composer-row">
              <textarea
                ref={inputRef}
                id="chat-input"
                data-testid="chat-input"
                rows={2}
                value={draftText}
                disabled={!canSendInCurrentView || chatBusy}
                placeholder={
                  !canInteract
                    ? isHistoryView
                      ? '历史旧档只读'
                      : '终局已归档'
                    : '颁旨垂询…'
                }
                onChange={(e) => onChangeDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    onSendMessage();
                  }
                }}
              />
              <button
                type="button"
                className="send-btn"
                id="send-chat"
                data-testid="send-chat-btn"
                disabled={
                  !canSendInCurrentView ||
                  chatBusy ||
                  draftText.trim() === ''
                }
                onClick={onSendMessage}
              >
                {chatBusy ? '传旨' : '降旨'}
              </button>
            </div>
          </div>
        </div>
      </section>

      {membersPopupOpen && activeConversation?.kind === 'group' && createPortal(
        <div
          className="modal-scrim"
          onClick={() => setMembersPopupOpen(false)}
        >
          <section
            ref={membersDialogRef}
            className="modal-card"
            id="group-members-window"
            role="dialog"
            aria-modal="true"
            aria-labelledby="group-members-dialog-title"
            tabIndex={-1}
            data-testid="group-members-dialog"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-head">
              <div>
                <h2 id="group-members-dialog-title">廷议成员</h2>
              </div>
              <button
                type="button"
                className="icon-close"
                aria-label="关闭"
                onClick={() => setMembersPopupOpen(false)}
              >
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M18 6 6 18" />
                  <path d="m6 6 12 12" />
                </svg>
              </button>
            </div>
            <div className="modal-body">
              <div className="member-list">
                {activeCharIds.map((charId) => {
                  const char = characterById.get(charId);
                  const officeTitle =
                    activeOfficeByCharacter.get(charId)?.title ?? '候任';
                  return (
                    <div key={charId} className="member-row">
                      <span
                        className={`portrait ${getCharacterPortraitClass(charId)}`}
                        aria-hidden="true"
                      />
                      <div className="member-row-copy">
                        <strong>{char?.name ?? charId}</strong>
                        <span>{officeTitle}</span>
                      </div>
                      {onOpenBiography && (
                        <button
                          type="button"
                          className="info-btn"
                          data-bio-person={charId}
                          title="生平"
                          aria-label={`${char?.name ?? charId}生平`}
                          onMouseEnter={(e) =>
                            onHoverBiography?.(charId, e.currentTarget)
                          }
                          onMouseLeave={(e) => onLeaveBiography?.(e.currentTarget)}
                          onBlur={() => onLeaveBiography?.()}
                          onClick={(e) => {
                            e.stopPropagation();
                            onOpenBiography(charId, e.currentTarget);
                          }}
                        >
                          <svg
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2.2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            aria-hidden="true"
                          >
                            <circle cx="12" cy="12" r="9" />
                            <path d="M12 11v5" />
                            <path d="M12 8h.01" />
                          </svg>
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </section>
        </div>,
        document.body
      )}

      {groupCreateOpen && createPortal(
        <div
          className="modal-scrim"
          onClick={() => setGroupCreateOpen(false)}
        >
          <section
            ref={groupCreateDialogRef}
            className="modal-card"
            id="group-create-window"
            role="dialog"
            aria-modal="true"
            aria-labelledby="group-create-dialog-title"
            tabIndex={-1}
            data-testid="group-create-dialog"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-head">
              <div>
                <h2 id="group-create-dialog-title">召集群臣廷议</h2>
              </div>
              <button
                type="button"
                className="icon-close"
                aria-label="关闭"
                onClick={() => setGroupCreateOpen(false)}
              >
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M18 6 6 18" />
                  <path d="m6 6 12 12" />
                </svg>
              </button>
            </div>
            <div className="modal-body">
              <label className="dialog-field" htmlFor="group-topic-input">
                <span>廷议议题</span>
                <input
                  id="group-topic-input"
                  type="text"
                  value={groupTitle}
                  onChange={(e) => setGroupTitle(e.target.value)}
                />
              </label>
              <div className="member-checks">
                {appointedCharacters.map((char) => {
                  const officeTitle =
                    activeOfficeByCharacter.get(char.character_id)?.title ?? '在任';
                  const checked = selectedGroupMemberIds.includes(
                    char.character_id
                  );
                  return (
                    <label key={char.character_id} className="member-check">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() =>
                          handleToggleNewGroupMember(char.character_id)
                        }
                      />
                      <span
                        className={`portrait ${getCharacterPortraitClass(char.character_id)}`}
                        aria-hidden="true"
                      />
                      <span className="member-check-copy">
                        <strong>{char.name}</strong>
                        <em>{officeTitle}</em>
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>
            <div className="modal-actions">
              <button
                type="button"
                className="send-btn"
                id="create-group-btn"
                disabled={chatBusy || selectedGroupMemberIds.length === 0}
                onClick={() => void handleConfirmCreateGroup()}
              >
                召集群臣
              </button>
            </div>
          </section>
        </div>,
        document.body
      )}
    </>
  );
};
